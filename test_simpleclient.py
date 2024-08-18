#!.venv/bin/python3
import socketio
import edwh


with socketio.SimpleClient(ssl_verify=False, logger=True, engineio_logger=True) as sio:
    sio.connect(edwh.get_env_value('SIO_URL'))
    while True:
        message, data = sio.receive()
        print(f"simple!> {message!r} - {data!r}")
        if message == 'exit':
            break
    sio.disconnect()