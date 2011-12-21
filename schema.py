#!/usr/bin/env python
import time
import settings

APP_KEY = 'applications:{0}:{1}'
LOG_KEY = 'logs:{0}:'.format(settings.NODE_NAME) + '{0}'
NODE_KEY = 'nodes:{0}'
NODE_APPS_KEY = '{0}:applications'.format(NODE_KEY)
PORTS_KEY = '{0}:ports'.format(NODE_KEY.format(settings.NODE_NAME))
ROLE_KEY = 'roles:{0}'
USER_KEY = 'users:{0}'
HEARTBEAT_KEY = 'heartbeat:{0}'.format(settings.NODE_NAME)

def user(username=None, first_name=None, last_name=None, email=None, \
    password=None, role=None, enabled=True):
    data = {
        'username': username,
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password': password,
        'role': role,
        'enabled': enabled,
    }
    return data

def role(rolename=None):
    return {'rolename': rolename}

def log(level=None, category='root', message=None):
    data = {
        'date': time.time(),
        'level': level,
        'category': category,
        'message': message,
    }
    return data
