#!/usr/bin/env python
import application
import schema
import logging
try:
    import simplejson as json
except ImportError:
    import json

class RedisHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, msg):
        db = application.get_db_connection()
        data = schema.log(msg.levelno, msg.name, msg.msg)
        log_key = schema.LOG_KEY.format('{0}:{1}'.format(data['category'], data['date']))
        db.set(log_key, json.dumps(data))

