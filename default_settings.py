import os
import logging
from flaskext.babel import gettext, lazy_gettext
import sys
sys.path.append('./')
try:
    import simplejson as json
except ImportError:
    import json

APP_NAME = 'terminus'
# add api keys here for api access
API_KEYS = (
    'defaultapikey',
)
DEBUG = True
# db
DB_HOST = 'localhost'
DB_PORT = 6379
DB_NAME = 0
DB_USER = '<DBUSER>'
DB_PASSWORD = '<DBPASS>'
LOCALES = ( 
    ('en', lazy_gettext(u'English')),
    ('fr', lazy_gettext(u'French')),
)
NODE_NAME = os.uname()[1]
PROJECT_PATH = os.path.dirname(__file__)
SECRET_KEY = "<SECRET_KEY>"
# queue settings
TASK_QUEUE_NAME = 'queue:{0}'.format(NODE_NAME)
TASK_QUEUE_KEY_TTL = 86400
# app version
VERSION = '0.1'

# vars
ROOT_DIR = '/var/tmp'
APP_MIN_PORT = 15000
APP_MAX_PORT = 40000
APPLICATION_BASE_DIR = os.path.join(ROOT_DIR, 'apps')
APPLICATION_USER = 'www-data'
APPLICATION_GROUP = 'www-data'
APPLICATION_LOG_DIR = os.path.join(ROOT_DIR, 'logs')
APPLICATION_STATE_DIR = os.path.join(ROOT_DIR, 'state')
CLIENT_CHANNEL = 'client'
HEARTBEAT_INTERVAL = 10 # in seconds
MASTER_CHANNEL = 'master'
VIRTUALENV_BASE_DIR = os.path.join(ROOT_DIR, 've')
SUPERVISOR_CONF_DIR = os.path.join(ROOT_DIR, 'supervisor')
WEBSERVER_CONF_DIR = os.path.join(ROOT_DIR, 'nginx')

try:
    from local_settings import *
except ImportError:
    pass
