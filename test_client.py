#!.venv/bin/python3
import os
import signal

import edwh
import socketio

sio = socketio.Client(ssl_verify=False, logger=True, engineio_logger=True)
sio.connect(edwh.get_env_value('SIO_URL'))


@sio.event
def connect():
    print('connection established')
    # sio.emit('test', {'data': 'some data'})


@sio.on('demo')
def test(data):
    print(f"!> DEMO@{sio.sid} {data!r}")


@sio.on('exit')
def stop_this_server(event, sid, data):
    os.kill(os.getpid(), signal.SIGINT)


@sio.on("*")
def cath_all(event, namespace, sid, data):
    print(f"!> CATCH ALL ns:{namespace} {event!r}@{sid} {data!r}")
#
# @sio.on("*",namespace='*')
# def catch_all_acros_all_ns(event, namespace, sid, data):
#     print(f"!> CATH ALL EVERYWHERE ns:{namespace} {event!r}@{sid} {data!r}")
#

@sio.event
def disconnect():
    print('disconnected from server')



while True:
    sio.wait()
