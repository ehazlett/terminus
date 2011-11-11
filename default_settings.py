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
# mongo
DB_HOST = 'localhost'
DB_PORT = 6379
DB_NAME = 0
DB_USER = '<DBUSER>'
DB_PASSWORD = '<DBPASS>'
# queue settings
TASK_QUEUE_NAME = 'queue'
TASK_QUEUE_KEY_TTL = 86400
# app version
VERSION = '0.1'
SECRET_KEY = "<SECRET_KEY>"

try:
    from local_settings import *
except ImportError:
    pass
