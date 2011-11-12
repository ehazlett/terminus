from flask import Flask
from flask import jsonify
from flask import json
from flask import request, Response
from flask import session
from flask import g
from flask import render_template
from flask import redirect, url_for
from flask import flash
import os
import uuid
import logging
import sys
import settings
from optparse import OptionParser
from getpass import getpass
import redis
import utils
from utils import deploy
import queue
import schema
import messages
from decorators import admin_required, login_required, api_key_required

app = Flask(__name__)
app.debug = settings.DEBUG
app.logger.setLevel(logging.ERROR)
app.config.from_object('settings')

@app.before_request
def before_request():
    g.db = get_db_connection()

@app.teardown_request
def teardown_request(exception):
    pass

def get_db_connection():
    return redis.Redis(host=app.config['DB_HOST'], port=app.config['DB_PORT'], \
        db=app.config['DB_NAME'], password=app.config['DB_PASSWORD'])

@app.route("/")
def index():
    if 'auth_token' in session:
        return render_template("index.html")
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

@app.route("/accounts/")
@admin_required
def accounts():
    users = [json.loads(g.db.get(x)) for x in g.db.keys(schema.USER_KEY.format('*'))]
    roles = [json.loads(g.db.get(x)) for x in g.db.keys(schema.ROLE_KEY.format('*'))]
    ctx = {
        'users': users,
        'roles': roles,
    }
    return render_template('users.html', **ctx)

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
    ctx = {
        'tasks': tasks,
    }
    return render_template("tasks.html", **ctx)

@app.route("/tasks/delete/<task_id>/")
@admin_required
def delete_task(task_id):
    # delete 'complete' key
    if task_id.find(':') > -1:
        g.db.delete(task_id)
    else: # task is 'new'
        task_id = int(task_id)
        if task_id == 0:
            g.db.lpop(app.config['TASK_QUEUE_NAME'])
        else: # hack -- rebuild list because `del lindex list <index>` doesn't work in redis-py
            pre = g.db.lrange(app.config['TASK_QUEUE_NAME'], 0, task_id-1)
            post = g.db.lrange(app.config['TASK_QUEUE_NAME'], task_id+1, -1)
            pre.reverse()
            post.reverse()
            g.db.delete(app.config['TASK_QUEUE_NAME'])
            [g.db.lpush(app.config['TASK_QUEUE_NAME'], x) for x in post]
            [g.db.lpush(app.config['TASK_QUEUE_NAME'], x) for x in pre]
    flash('Task deleted...', 'success')
    return redirect(url_for('tasks'))

@app.route("/tasks/deleteall/")
@admin_required
def delete_all_tasks():
    g.db.delete(app.config['TASK_QUEUE_NAME'])
    for k in g.db.keys('{0}:*'.format(app.config['TASK_QUEUE_NAME'])):
        g.db.delete(k)
    flash('All tasks removed...', 'success')
    return redirect(url_for('tasks'))

# ----- API -----
@app.route("/api/<action>", methods=['GET', 'POST'])
@api_key_required
def api(action=None):
    if action.lower() == 'version':
        return jsonify({'name': app.config['APP_NAME'], 'version': app.config['VERSION']})
    elif action.lower() == 'deploy':
        data = {}
        data['task_id'] = deploy.deploy_app.delay('testpackage').key
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

if __name__=="__main__":
    op = OptionParser()
    op.add_option('--create-user', dest='create_user', action='store_true', default=False, help='Create/update user')
    op.add_option('--enable-user', dest='enable_user', action='store_true', default=False, help='Enable user')
    op.add_option('--disable-user', dest='disable_user', action='store_true', default=False, help='Disable user')
    opts, args = op.parse_args()

    if opts.create_user:
        create_user()
        sys.exit(0)
    if opts.enable_user:
        toggle_user(True)
        sys.exit(0)
    if opts.disable_user:
        toggle_user(False)
        sys.exit(0)
    # run app
    app.run()


