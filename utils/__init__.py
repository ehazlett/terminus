import hashlib
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
    data = schema.user(username=username, email=email, \
        password=encrypt_password(password, settings.SECRET_KEY), \
        role=role, enabled=enabled)
    db.users.insert(data)
    return True

def create_role(rolename=None):
    if not rolename:
        raise NameError('You must specify a rolename')
    db = application.get_db_connection()
    data = schema.role(rolename)
    db.roles.insert(data)
    return True

def delete_user(username=None):
    if not username:
        raise NameError('You must specify a username')
    db = application.get_db_connection()
    db.users.remove({'username': username})
    return True

def delete_role(rolename=None):
    if not rolename:
        raise NameError('You must specify a rolename')
    db = application.get_db_connection()
    db.roles.delete(schema.role(rolename=rolename))
    return True

def toggle_user(username=None, enabled=None):
    if not username:
        raise NameError('You must specify a username')
    db = application.get_db_connection()
    user = db.users.find_one({'username': username})
    if user:
        if enabled != None:
            user['enabled'] = enabled
        else:
            current_status = user['enabled']
            if current_status:
                enabled = False
            else:
                enabled = True
        db.users.update({'username': username}, {"$set": {'enabled': enabled} })
        return True
    else:
        raise RuntimeError('User not found')


def encrypt_password(password=None, salt=None):
    h = hashlib.sha256(salt)
    h.update(password+salt)
    return h.hexdigest()
