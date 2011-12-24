import hashlib
from random import Random
import schema
import application
import settings
try:
    import simplejson as json
except ImportError:
    import json

def create_user(username=None, email=None, password=None, role=None, enabled=True):
    if not username or not password or not role:
        raise NameError('You must specify a username, password, and role')
    db = application.get_db_connection()
    user_key = schema.USER_KEY.format(username)
    data = schema.user(username=username, email=email, \
        password=encrypt_password(password, settings.SECRET_KEY), \
        role=role, enabled=enabled)
    db.set(user_key, json.dumps(data))
    return True

def get_user(username=None):
    if not username:
        raise NameError('You must specify a username')
    db = application.get_db_connection()
    user_key = schema.USER_KEY.format(username)
    return db.get(user_key)

def delete_user(username=None):
    if not username:
        raise NameError('You must specify a username')
    db = application.get_db_connection()
    user_key = schema.USER_KEY.format(username)
    db.delete(user_key)
    return True

def create_role(rolename=None):
    if not rolename:
        raise NameError('You must specify a rolename')
    db = application.get_db_connection()
    role_key = schema.ROLE_KEY.format(rolename)
    data = schema.role(rolename)
    db.set(role_key, json.dumps(data))
    return True

def get_role(rolename=None):
    if not rolename:
        raise NameError('You must specify a rolename')
    db = application.get_db_connection()
    role_key = schema.ROLE_KEY.format(rolename)
    return db.get(role_key)

def delete_role(rolename=None):
    if not rolename:
        raise NameError('You must specify a rolename')
    db = application.get_db_connection()
    role_key = schema.ROLE_KEY.format(rolename)
    db.delete(role_key)
    return True

def toggle_user(username=None, enabled=None):
    if not username:
        raise NameError('You must specify a username')
    db = application.get_db_connection()
    user_key = schema.USER_KEY.format(username)
    user = db.get(user_key)
    if user:
        user_data = json.loads(user)
        if enabled != None:
            user_data['enabled'] = enabled
        else:
            current_status = user_data['enabled']
            if current_status:
                enabled = False
            else:
                enabled = True
            user_data['enabled'] = enabled
        db.set(user_key, json.dumps(user_data))
        return True
    else:
        raise RuntimeError('User not found')

def encrypt_password(password=None, salt=None):
    h = hashlib.sha256(salt)
    h.update(password+salt)
    return h.hexdigest()

def get_task(task_id=None):
    if not task_id:
       raise NameError('You must specify a task id')
    db = application.get_db_connection()
    task_key = '{0}:{1}'.format(settings.TASK_QUEUE_NAME, task_id)
    return db.get(task_key)

def get_application_config(app=None):
    if not application:
        raise NameError('You must specify an application')
    db = application.get_db_connection()
    app_key = schema.APP_KEY.format(app, '*')
    res = db.keys(app_key)
    if res:
        app = db.get(res[0])
    else:
        app = None
    return app

def update_application_config(app=None, config={}):
    if not application:
        raise NameError('You must specify an application')
    db = application.get_db_connection()
    app_key = schema.APP_KEY.format(app, '')
    db.set(app_key, json.dumps(config))
    return True

def remove_application_config(app=None):
    if not application:
        raise NameError('You must specify an application')
    db = application.get_db_connection()
    app_key = schema.APP_KEY.format(app, '*')
    res = db.keys(app_key)
    for k in res:
        db.delete(k)
    return True

def get_next_application_port():
    db = application.get_db_connection()
    k = schema.PORTS_KEY
    port = None
    ports = db.get(k)
    if not ports:
        ports = []
    else:
        try:
            ports = json.loads(ports)
        except:
            ports = []
    # generate and make sure port not already used
    while True:
        port = Random().randint(settings.APP_MIN_PORT, settings.APP_MAX_PORT)
        if port not in ports:
            break
    return port

def reserve_application_port(port=None):
    if not port:
        raise NameError('You must specify a port')
    db = application.get_db_connection()
    ports = db.get(schema.PORTS_KEY)
    if not ports:
        ports = []
    else:
        try:
            ports = json.loads(ports)
        except:
            ports = []
    if port in ports:
        raise RuntimeError('Port already reserved')
    ports.append(port)
    db.set(schema.PORTS_KEY, json.dumps(ports))
    return True

def release_application_port(port=None):
    if not port:
        raise NameError('You must specify a port')
    db = application.get_db_connection()
    ports = db.get(schema.PORTS_KEY)
    if ports:
        try:
            ports = json.loads(ports)
            ports.remove(port)
            db.set(schema.PORTS_KEY, json.dumps(ports))
        except:
            pass

def add_app_to_node_app_list(app_name=None):
    if not app_name:
        raise NameError('You must specify an application name')
    db = application.get_db_connection()
    db.sadd(schema.NODE_APPS_KEY.format(settings.NODE_NAME), app_name)
    return True

def remove_app_from_node_app_list(app_name=None):
    if not app_name:
        raise NameError('You must specify an application name')
    db = application.get_db_connection()
    db.srem(schema.NODE_APPS_KEY.format(settings.NODE_NAME), app_name)
    return True

def publish_client_message(msg={}):
    if not msg:
        raise NameError('You must specify a message')
    db = application.get_db_connection()
    # check type
    if not isinstance(msg, dict):
        msg = {'data': msg}
    db.publish(settings.CLIENT_CHANNEL, json.dumps(msg))
    return True

def get_node_applications(node_name=settings.NODE_NAME):
    if not node_name:
        raise NameError('You must specify a node_name')
    db = application.get_db_connection()
    return db.smembers(schema.NODE_APPS_KEY.format(node_name))

