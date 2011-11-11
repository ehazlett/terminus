#!/usr/bin/env python
import application
import schema
import time
try:
    import simplejson as json
except ImportError:
    import json

def log_message(level=None, category=None, message=None):
    """
    Logs message

    :keyword level: Level of message
    :keyword application: Name of application
    :keyword message: Message to log

    """
    db = application.get_db_connection()
    data = schema.log(level, category, message)
    log_key = schema.LOG_KEY.format('{0}:{1}'.format(category, data['date']))
    db.set(log_key, json.dumps(data))
