#!.venv/bin/python3
import asyncio
import os
import signal

import uvicorn
import socketio
import logging
import edwh
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

PORT = int(edwh.get_env_value("SIO_PORT", '31979'))
HOST = edwh.get_env_value("SIO_HOST", "127.0.0.1")
SERV_APP_FILE = "sioserver:app"

logger.debug(f"===: {SERV_APP_FILE}")

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    SameSite=None,
    logger=True,
    engineio_logger=True,
)

# host the index.html as the basis, include sio.js with all it's files under the /sio.js folder.
app = socketio.ASGIApp(sio, static_files={"/": "./index.html", "/test":"./test.html", '/src':'./src/'})

# message handlers message handlers message handlers message handlers message handlers message handlers message

@sio.on('exit')
async def stop_this_server(event, sid, data):
    await sio.emit(event, data)
    asyncio.sleep(3)
    import os
    os.kill(os.getpid(), signal.SIGINT)
    os.kill(os.getpid(), signal.SIGINT)
    os.kill(os.getpid(), signal.SIGINT)

@sio.on("*")
async def broadcast(event, sid, data):
    logger.info(f"!> CATCHALL BROADCASTER {event!r}@{sid} {data!r}")
    await sio.emit(event, data)


# main main main main main main main main main main main main main main main main main main main main main main main
if __name__ == "__main__":
    uvicorn.run(
        app=SERV_APP_FILE,
        host=HOST,
        port=PORT,
        reload=True,
        workers=1,
    )
