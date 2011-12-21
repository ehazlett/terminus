from flask import Flask
from flask import jsonify
from flask import json
from flask import request, Response
from flask import session
from flask import g
from flask import render_template
from flask import redirect, url_for
from flask import flash
from flaskext.babel import Babel
from flaskext.babel import format_datetime
import os
import uuid
import logging
import shutil
import sys
import settings
from optparse import OptionParser
from subprocess import call, Popen, PIPE
from getpass import getpass
import tempfile
import time
from datetime import datetime
from random import Random
import string
import redis
import utils
import hashlib
from utils import deploy, config
from utils.log import RedisHandler
import queue
import schema
import messages
from decorators import admin_required, login_required, api_key_required

app = Flask(__name__)
app.debug = settings.DEBUG
app.logger.setLevel(logging.ERROR)
app.config.from_object('settings')
# extensions
babel = Babel(app)

# redis handler
redis_handler = RedisHandler()
redis_handler.setLevel(logging.DEBUG)
app.logger.addHandler(redis_handler)

api_log = config.get_logger('api')
console_log = config.get_logger('console')
startup_log = config.get_logger('boot')
log = config.get_logger('webui')

# ----- filters -----
@app.template_filter('date_from_timestamp')
def date_from_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).strftime('%b %d, %Y %H:%M:%S.%f')

# ----- end filters ----

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    pass

def get_db_connection():
    return redis.Redis(host=app.config['DB_HOST'], port=app.config['DB_PORT'], \
        db=app.config['DB_NAME'], password=app.config['DB_PASSWORD'])

@babel.localeselector
def get_locale():
    # if a user is logged in, use the locale from the account
    if session.has_key('user'):
        user = json.loads(g.db.get(schema.USER_KEY.format(session['user'])))
        if user.has_key('locale'):
            return user['locale']
    # otherwise try to guess the language from the user accept
    # header the browser sends
    return request.accept_languages.best_match([x[0] for x in app.config['LOCALES']])

@app.route("/")
def index():
    if 'auth_token' in session:
        ctx = {}
        try:
            applications = utils.get_node_applications()
            apps = []
            for app in applications:
                json_data = json.loads(utils.get_application_config(app))
                app_data = {
                    'name': app,
                    'version': json_data['version'],
                    'instances': json_data['instances'][settings.NODE_NAME],
                    'runtime': json_data['runtime'],
                }
                apps.append(app_data)
            ctx = {
                'applications': apps,
            }
        except Exception, e:
            import traceback
            traceback.print_exc()
            flash(e, 'error')
        return render_template("index.html", **ctx)
    else:
        return redirect(url_for('about'))

@app.route("/about/")
def about():
    return render_template("about.html")

@app.route("/login/", methods=['GET', 'POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    user_key = schema.USER_KEY.format(username)
    user = g.db.get(user_key)
    if not user:
        flash(messages.INVALID_USERNAME_PASSWORD, 'error')
    else:
        user_data = json.loads(user)
        if utils.encrypt_password(password, app.config['SECRET_KEY']) == user_data['password']:
            if not user_data['enabled']:
                flash(messages.USER_ACCOUNT_DISABLED, 'error')
            else:
                auth_token = str(uuid.uuid4())
                user_data['auth_token'] = auth_token
                session['user'] = username
                session['role'] = user_data['role']
                session['auth_token'] = auth_token
                g.db.set(user_key, json.dumps(user_data))
        else:
            flash(messages.INVALID_USERNAME_PASSWORD, 'error')
    return redirect(url_for('index'))

@app.route("/logout/", methods=['GET'])
def logout():
    if 'auth_token' in session:
        session.pop('auth_token')
    if 'role' in session:
        session.pop('role')
    if 'user' in session:
        user_key = schema.USER_KEY.format(session['user'])
        user = g.db.get(user_key)
        user_data = json.loads(user)
        user_data['auth_token'] = None
        g.db.set(user_key, json.dumps(user_data))
        session.pop('user')
        flash(messages.LOGGED_OUT)
    return redirect(url_for('index'))

@app.route("/account/", methods=['GET', 'POST'])
@login_required
def account():
    if 'user' in session:
        user_key = schema.USER_KEY.format(session['user'])
        account = json.loads(utils.get_user(session['user']))
        if request.method == 'GET':
            ctx = {
                'account': account,
                'locales': app.config['LOCALES'],
            }
            return render_template('account.html', **ctx)
        else:
            for k in request.form:
                account[k] = request.form[k]
            g.db.set(user_key, json.dumps(account))
            flash(messages.ACCOUNT_UPDATED, 'success')
    return redirect(url_for('account'))

@app.route("/accounts/")
@admin_required
def accounts():
    users = [json.loads(g.db.get(x)) for x in g.db.keys(schema.USER_KEY.format('*'))]
    roles = [json.loads(g.db.get(x)) for x in g.db.keys(schema.ROLE_KEY.format('*'))]
    ctx = {
        'users': users,
        'roles': roles,
    }
    return render_template('accounts.html', **ctx)

@app.route("/accounts/adduser/", methods=['POST'])
@admin_required
def add_user():
    form = request.form
    try:
        utils.create_user(username=form['username'], email=form['email'], \
            password=form['password'], role=form['role'], enabled=True)
        flash(messages.USER_CREATED, 'success')
    except Exception, e:
        flash('{0} {1}'.format(messages.NEW_USER_ERROR, e), 'error')
    return redirect(url_for('accounts'))

@app.route("/accounts/toggleuser/<username>/")
@admin_required
def toggle_user(username):
    try:
        utils.toggle_user(username)
    except Exception, e:
        app.logger.error(e)
        flash('{0} {1}'.format(messages.ERROR_DISABLING_USER, e), 'error')
    return redirect(url_for('accounts'))

@app.route("/accounts/deleteuser/<username>/")
@admin_required
def delete_user(username):
    try:
        utils.delete_user(username)
        flash(messages.USER_DELETED, 'success')
    except Exception, e:
        flash('{0} {1}'.format(messages.ERROR_DELETING_USER, e), 'error')
    return redirect(url_for('accounts'))

@app.route("/accounts/addrole/", methods=['POST'])
@admin_required
def add_role():
    form = request.form
    try:
        utils.create_role(form['rolename'])
        flash(messages.ROLE_CREATED, 'success')
    except Exception, e:
        flash('{0} {1}'.format(messages.NEW_ROLE_ERROR, e), 'error')
    return redirect(url_for('accounts'))

@app.route("/users/deleterole/<rolename>/")
@admin_required
def delete_role(rolename):
    try:
        utils.delete_role(rolename)
        flash(messages.ROLE_DELETED, 'success')
    except Exception, e:
        flash('{0} {1}'.format(messages.ERROR_DELETING_ROLE, e), 'error')
    return redirect(url_for('accounts'))

@app.route("/tasks/")
@admin_required
def tasks():
    tasks = []
    for t in g.db.keys('{0}:*'.format(app.config['TASK_QUEUE_NAME'])):
        tasks.append(json.loads(g.db.get(t)))
    num_of_queued = g.db.llen(app.config['TASK_QUEUE_NAME'])
    if num_of_queued > 0:
        for i in range(num_of_queued):
            # generate unique hash for key -- used to delete
            task_data = g.db.lindex(app.config['TASK_QUEUE_NAME'], i)
            sha = hashlib.sha256(task_data)
            task_hash = sha.hexdigest()
            data = {}
            data['task'] = task_data
            data['task_id'] = task_hash
            data['date'] = None
            data['status'] = 'new'
            tasks.append(data)
    ctx = {
        'tasks': tasks,
    }
    return render_template("tasks.html", **ctx)

@app.route("/tasks/delete/<task_id>/")
@admin_required
def delete_task(task_id=None):
    # delete 'complete' key
    key = '{0}:{1}'.format(app.config['TASK_QUEUE_NAME'], task_id)
    if task_id and g.db.get(key):
        g.db.delete(key)
    else: # task is 'new'
        # generate hash to find key
        for k in range(g.db.llen(app.config['TASK_QUEUE_NAME'])):
            task_data = g.db.lindex(app.config['TASK_QUEUE_NAME'], k)
            sha = hashlib.sha256(task_data)
            task_hash = sha.hexdigest()
            if task_hash == task_id:
                g.db.lrem(app.config['TASK_QUEUE_NAME'], task_data)
    log.info('{0} deleted task {1}'.format(session['user'], task_id))
    flash('Task deleted...', 'success')
    return redirect(url_for('tasks'))

@app.route("/tasks/deleteall/")
@admin_required
def delete_all_tasks():
    g.db.delete(app.config['TASK_QUEUE_NAME'])
    for k in g.db.keys('{0}:*'.format(app.config['TASK_QUEUE_NAME'])):
        g.db.delete(k)
    flash('All tasks removed...')
    return redirect(url_for('tasks'))

@app.route("/logs/")
@admin_required
def logs():
    logs = []
    log_key = schema.LOG_KEY.format('*')
    for l in g.db.keys(log_key):
        logs.append(json.loads(g.db.get(l)))
    ctx = {
        'logs': logs,
    }
    return render_template("logs.html", **ctx)

@app.route("/logs/clear/")
@admin_required
def clear_logs():
    for k in g.db.keys(schema.LOG_KEY.format('*')):
        g.db.delete(k)
    flash('Logs cleared...')
    return redirect(url_for('logs'))


# ----- API -----
@app.route("/api/manage/<action>", methods=['GET', 'POST'])
@api_key_required
def api(action=None):
    data = {}
    try:
        if not action:
            raise NameError('You must specify an action')
        action = action.lower()
        if action == 'version':
            return jsonify({'name': app.config['APP_NAME'], 'version': app.config['VERSION']})
        elif action.lower() == 'deploy':
            data = {}
            f = request.files['package']
            pkg_name = tempfile.mktemp()
            f.save(pkg_name)
            data['task_id'] = deploy.deploy_app.delay(pkg_name).key
        elif action == 'restart':
            data = {}
            if 'application' not in request.form:
                raise NameError('You must specify an application')
            app_name = request.form['application']
            data['task_id'] = deploy.restart_application.delay(app_name).key
        elif action == 'stop':
            data = {}
            if 'application' not in request.form:
                raise NameError('You must specify an application')
            app_name = request.form['application']
            data['task_id'] = deploy.stop_application.delay(app_name).key
        elif action == 'remove':
            data = {}
            if 'application' not in request.form:
                raise NameError('You must specify an application')
            app_name = request.form['application']
            data['task_id'] = deploy.remove_application.delay(app_name).key
        else:
            print('Unknown action: {0}'.format(action))
            data['status'] = 'error'
            data['result'] = 'unknown action'
    except Exception, e:
        data = {'status': 'error', 'result': str(e)}
    return jsonify(data)

@app.route("/api/task/<task_id>/", methods=['GET', 'POST'])
@api_key_required
def api_task(task_id=None):
    try:
        task = utils.get_task(task_id)
        try:
            data = json.loads(task)
        except Exception, e:
            data = {'status': 'error', 'result': 'invalid task'}
    except Exception, e:
        data = {'status': 'error', 'result': str(e)}
    return jsonify(data)

@app.route("/api/generateapikey/")
@login_required
def api_generate_apikey():
    data = {
        "key": ''.join(Random().sample(string.letters+string.digits, 32)),
    }
    return jsonify(data)

# ----- END API -----

# ----- management commands -----
def create_user():
    db = get_db_connection()
    try:
        username = raw_input('Username: ').strip()
        email = raw_input('Email: ').strip()
        while True:
            password = getpass('Password: ')
            password_confirm = getpass(' (confirm): ')
            if password_confirm == password:
                break
            else:
                print('Passwords do not match... Try again...')
        role = raw_input('Role: ').strip()
        # create role if needed
        if not db.get(schema.ROLE_KEY.format(role)):
            utils.create_role(role)
        utils.create_user(username=username, email=email, password=password, \
            role=role, enabled=True)
        print('User created/updated successfully...')
    except KeyboardInterrupt:
        pass

def toggle_user(active):
    try:
        username = raw_input('Enter username: ').strip()
        try:
            utils.toggle_user(username, active)
        except Exception, e:
            print(e)
            sys.exit(1)
    except KeyboardInterrupt:
        pass

def generate_supervisor_conf():
    """
    Generates the supervisord config

    """
    conf = '; {0} supervisor config\n\n'.format(settings.APP_NAME)
    conf += '[unix_http_server]\n'
    conf += 'file={0}\n\n'.format(os.path.join(settings.SUPERVISOR_CONF_DIR, 'supervisor.sock'))
    conf += '[supervisord]\n'
    conf += 'childlogdir={0}\n'.format(settings.APPLICATION_LOG_DIR)
    conf += 'logfile={0}\n'.format(os.path.join(settings.SUPERVISOR_CONF_DIR, 'supervisord.log'))
    conf += 'logfile_maxbytes=50MB\n'
    conf += 'logfile_backups=5\n'
    conf += 'loglevel=info\n'
    conf += 'pidfile={0}\n'.format(os.path.join(settings.SUPERVISOR_CONF_DIR, 'supervisord.pid'))
    conf += 'nodaemon=false\n\n'
    conf += '[rpcinterface:supervisor]\n'
    conf += 'supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface\n\n'
    conf += '[supervisorctl]\n'
    conf += 'serverurl=unix://{0}\n\n'.format(os.path.join(settings.SUPERVISOR_CONF_DIR, \
        'supervisor.sock'))
    conf += '[include]\n'
    conf += 'files = {0}/*.conf\n'.format(settings.SUPERVISOR_CONF_DIR)
    with open('supervisord.conf', 'w') as f:
        f.write(conf)
    
def start_supervisor():
    """
    Starts supervisor

    """
    generate_supervisor_conf()
    # check for existing pid
    pid_file = os.path.join(settings.SUPERVISOR_CONF_DIR, 'supervisord.pid')
    sock_file = os.path.join(settings.SUPERVISOR_CONF_DIR, 'supervisor.sock')
    if os.path.exists(pid_file):
        startup_log.debug('Stopping supervisord')
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
        try:
            if pid != '':
                os.kill(int(pid), 9)
                # remove socket
        except Exception, e:
            startup_log.warn(str(e))
    if os.path.exists(sock_file):
        os.remove(sock_file)
    # start
    startup_log.debug('Starting supervisord')
    p = Popen(['supervisord', '-c', 'supervisord.conf'], stdout=PIPE, stderr=PIPE)
    p_out, p_err = p.stdout.read().strip(), p.stderr.read().strip()
    if p_out != '':
        startup_log.debug(p_out)
    if p_err != '':
        startup_log.error(p_err)
    # write pid if needed
    if not os.path.exists(pid_file):
        f = open(pid_file, 'w')
        f.write(p.pid)
        f.close()

def check_app_dirs():
    """
    Creates application directories if needed

    """
    dirs = (
        settings.APPLICATION_BASE_DIR,
        settings.APPLICATION_LOG_DIR,
        settings.APPLICATION_STATE_DIR,
        settings.VIRTUALENV_BASE_DIR,
        settings.SUPERVISOR_CONF_DIR,
        settings.WEBSERVER_CONF_DIR,
    )
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
    # copy nginx supporting files
    mime_types = os.path.join(settings.WEBSERVER_CONF_DIR, 'mime.types')
    uwsgi_params = os.path.join(settings.WEBSERVER_CONF_DIR, 'uwsgi_params')
    template_dir = os.path.join(settings.PROJECT_PATH, 'templates')
    if not os.path.exists(mime_types):
        shutil.copy(os.path.join(template_dir, 'mime.types'), mime_types)
    if not os.path.exists(uwsgi_params):
        shutil.copy(os.path.join(template_dir, 'uwsgi_params'), uwsgi_params)
    
if __name__=="__main__":
    op = OptionParser()
    op.add_option('--create-user', dest='create_user', action='store_true', default=False, help='Create/update user')
    op.add_option('--enable-user', dest='enable_user', action='store_true', default=False, help='Enable user')
    op.add_option('--disable-user', dest='disable_user', action='store_true', default=False, help='Disable user')
    op.add_option('--host', dest='host', default='localhost', help='Host to listen on for the Werkzeug debug server')
    op.add_option('--port', dest='port', default='5000', help='Port to run Werkzeug debug server')
    opts, args = op.parse_args()

    # check app dirs
    check_app_dirs()
    if opts.create_user:
        create_user()
        sys.exit(0)
    if opts.enable_user:
        toggle_user(True)
        sys.exit(0)
    if opts.disable_user:
        toggle_user(False)
        sys.exit(0)
    # start supervisor
    start_supervisor()
    # run app
    app.run(host=opts.host, port=int(opts.port))


