#!/usr/bin/env python
from application import get_db_connection
from multiprocessing import Process
from subprocess import call, Popen, PIPE
import os
import settings
import utils
import schema
import time
try:
    import simplejson as json
except ImportError:
    import json

def master_listener():
    db = get_db_connection()
    ps = db.pubsub()
    # subscribe to master channel
    ps.subscribe(settings.MASTER_CHANNEL)
    # publish availability
    data = {'node': settings.NODE_NAME, 'status': 'available', 'version': settings.VERSION}
    utils.publish_client_message(data)
    for m in ps.listen():
        print(m)

def heartbeat():
    db = get_db_connection()
    data = {
        'node': settings.NODE_NAME, 
        'action': 'heartbeat', 
        'status': 'available', 
        'version': settings.VERSION,
        'load': os.getloadavg(),
    }
    k = schema.HEARTBEAT_KEY
    while True:
        db.set(k, json.dumps(data))
        db.expire(k, settings.HEARTBEAT_INTERVAL)
        time.sleep(settings.HEARTBEAT_INTERVAL)

def start_client_messaging():
    p = Process(target=heartbeat)
    p.start()

if __name__=='__main__':
    print('MQ up...')
    try:
        p = Process(target=master_listener)
        p.start()
        start_client_messaging()
    except KeyboardInterrupt:
        p.terminate()
