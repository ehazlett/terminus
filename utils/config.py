#!/usr/bin/env python
import logging

def get_logger(name=''):
    import application
    from application import app
    log = logging.getLogger(name)
    log.setLevel(app.config['LOG_LEVEL'])
    log.addHandler(application.redis_handler)
    return log
