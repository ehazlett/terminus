#!/usr/bin/env python
import application
import time

def log_message(level=None, handler=None, message=None):
    """
    Logs message to Mongo

    :keyword level: Level of message
    :keyword application: Name of application
    :keyword message: Message to log

    """
    db = get_db_connection()
    data = {
        "date": time.time(),
        "level": level,
        "handler": handler,
        "message": message,
    }
    db.logs.insert(data)
