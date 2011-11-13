import os
import logging
import sys
sys.path.append('./')
try:
    import simplejson as json
except ImportError:
    import json

APP_NAME = 'minion'
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
NODE_NAME = os.uname()[1]
SECRET_KEY = "<SECRET_KEY>"
# queue settings
TASK_QUEUE_NAME = 'queue:{0}'.format(NODE_NAME)
TASK_QUEUE_KEY_TTL = 86400
# app version
VERSION = '0.1'

# directory vars
APPLICATION_BASE_DIR = '/var/tmp/apps'
APPLICATION_USER = 'www-data'
APPLICATION_GROUP = 'www-data'
VIRTUALENV_BASE_DIR = '/var/tmp/ve'
SUPERVISOR_CONF_DIR = '/var/tmp/supervisor'
WEBSERVER_CONF_DIR = '/var/tmp/nginx'

try:
    from local_settings import *
except ImportError:
    pass
