#!/usr/bin/env
import application
import pickle
import uuid
import settings

class DelayedResult(object):
    def __init__(self, key):
        self.db = application.get_db_connection()
        self.key = key
        self._rv = None

    @property
    def return_value(self):
        if self._rv is None:
            rv = self.db[settings.TASK_QUEUE_NAME].find_one({'key': self.key})
            if rv is not None:
                self._rv = pickle.loads(rv['data'])
        return self._rv

def task(f):
    def delay(*args, **kwargs):
        db = application.get_db_connection()
        key = str(uuid.uuid4())
        s = pickle.dumps((f, key, args, kwargs))
        data = {'key': key, 'data': s}
        db[settings.TASK_QUEUE_NAME].insert(data)
        return DelayedResult(key)
    f.delay = delay
    return f

def queue_daemon(app):
    db = application.get_db_connection()
    while True:
        msg = redis.blpop(settings.REDIS_QUEUE_KEY)
        msg = db[settings.TASK_QUEUE_NAME].find_one()
        print('Running task: {0}'.format(msg['key']))
        func, key, args, kwargs = pickle.loads(msg['data'])
        try:
            rv = func(*args, **kwargs)
        except Exception, e:
            rv = e
        if rv is not None:
            msg.update({'data': rv})

if __name__=='__main__':
    from application import app
    print('Starting queue...')
    try:
        queue_daemon(app)
    except KeyboardInterrupt:
        print('Exiting...')

