#!/usr/bin/env
from flask import current_app
from flask import json
import application
import pickle
import uuid
import time
import settings

class DelayedResult(object):
    def __init__(self, key):
        self.db = application.get_db_connection()
        self.key = key
        self._rv = None

    @property
    def return_value(self):
        if self._rv is None:
            rv = self.db.get('{0}:{1}'.format(self.key))
            if rv is not None:
                self._rv = pickle.loads(rv)
        return self._rv

def task(f):
    def delay(*args, **kwargs):
        db = application.get_db_connection()
        qkey = settings.TASK_QUEUE_NAME
        task_id = str(uuid.uuid4())
        key = '{0}:{1}'.format(qkey, task_id)
        s = pickle.dumps((f, task_id, args, kwargs))
        db.rpush(settings.TASK_QUEUE_NAME, s)
        return DelayedResult(task_id)
    f.delay = delay
    return f

def queue_daemon(app, rv_ttl=settings.TASK_QUEUE_KEY_TTL):
    db = application.get_db_connection()
    while True:
        msg = db.blpop(settings.TASK_QUEUE_NAME)
        print('Running task: {0}'.format(msg))
        func, task_id, args, kwargs = pickle.loads(msg[1])
        qkey = settings.TASK_QUEUE_NAME
        key = '{0}:{1}'.format(qkey, task_id)
        data = {'date': time.time(), 'task_id': task_id, 'status': 'running', 'result': None}
        db.set(key, json.dumps(data))
        try:
            rv = func(*args, **kwargs)
            data['status'] = 'complete'
        except Exception, e:
            import traceback
            traceback.print_exc()
            rv = e
            data['status'] = 'error'
        if isinstance(rv, dict):
            rv = json.dumps(rv)
        else:
            rv = str(rv)
        data['result'] = rv
        if rv is not None:
            db.set(key, json.dumps(data))
            db.expire(key, rv_ttl)

if __name__=='__main__':
    from application import app
    print('Starting queue...')
    try:
        queue_daemon(app)
    except KeyboardInterrupt:
        print('Exiting...')

