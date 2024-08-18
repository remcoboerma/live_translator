#!.venv/bin/python3
import socketio



with socketio.SimpleClient(ssl_verify=False, logger=True, engineio_logger=True) as sio:
    sio.connect('http://127.0.0.1:31979')
    while True:
        event = sio.receive()
        print(f"simple!> {event!r}")
