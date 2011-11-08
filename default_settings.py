import os
import logging
import sys
sys.path.append('./')
try:
    import simplejson as json
except ImportError:
    import json

DEBUG = True
# mongo
DB_HOST = 'localhost'
DB_PORT = 27017
DB_NAME = 'aristotle'
DB_USER = 'aristotle'
DB_PASSWORD = '1q2w3e4r5t'
# queue settings
TASK_QUEUE_NAME = 'queue'
# app version
VERSION = '0.1'
SECRET_KEY = "HQchIex0baL9oZ]+Aw>}t|(mlYGB)V"
