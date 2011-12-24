#!/usr/bin/env python
import application
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
    db = application.get_db_connection()
    ps = db.pubsub()
    # subscribe to master channel
    ps.subscribe(settings.MASTER_CHANNEL)
    # publish availability
    data = {'node': settings.NODE_NAME, 'status': 'available', 'version': settings.VERSION}
    utils.publish_client_message(data)
    for m in ps.listen():
        print(m)

def heartbeat():
    db = application.get_db_connection()
    k = schema.HEARTBEAT_KEY
    while True:
        data = {
            'node': settings.NODE_NAME, 
            'address': settings.NODE_ADDRESS,
            'port': settings.NODE_PORT,
            'action': 'heartbeat', 
            'status': 'available', 
            'version': settings.VERSION,
            'load': os.getloadavg(),
        }
        db.set(k, json.dumps(data))
        db.expire(k, settings.HEARTBEAT_INTERVAL)
        time.sleep(settings.HEARTBEAT_INTERVAL)

def start_client_messaging():
    p = Process(target=heartbeat)
    p.start()

def main():
    p = Process(target=master_listener)
    p.start()
    start_client_messaging()

if __name__=='__main__':
    print('MQ up...')
    try:
        main()
    except KeyboardInterrupt:
        p.terminate()
