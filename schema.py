#!/usr/bin/env python
import time

USER_KEY = 'users:{0}'
ROLE_KEY = 'roles:{0}'
LOG_KEY = 'logs:{0}'

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
