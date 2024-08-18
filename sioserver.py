#!.venv/bin/python3
import os
import uvicorn
import socketio
import logging

# --------------- global ------------------------------------------

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

PORT = int(os.getenv("SIO_PORT", 31979))
HOST = os.getenv("SIO_HOST", "127.0.0.1")
SERV_APP_FILE = "sioserver:app"

logger.debug(f"===: {SERV_APP_FILE}")

# ------------------------------------
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    SameSite=None,
    logger=True,
    engineio_logger=True,
)

# https://github.com/abersheeran/a2wsgi

app = socketio.ASGIApp(sio, static_files={"/": "./index.html", '/sio.js':'./sio.js/'})


@sio.on("demo")
async def demo(sid, data):
    logger.info(f"!> DEMO HANDLER@{sid} {data!r}")
    await sio.emit('demo', data)

@sio.on("*")
async def collect_finals(event, sid, data):
    logger.info(f"!> CATCHALL HANDLER {event!r}@{sid} {data!r}")
    await sio.emit(event, data)

    # async def messageReceived(
    #     methods=["GET", "POST"],
    # ):
    #     logger.debug("final was received!!!")
    # await sio.emit("my_response", json, )
    # await sio.emit("my_response", json, room=sid, callback=messageReceived)

if __name__ == "__main__":
    uvicorn.run(
        app=SERV_APP_FILE,
        host=HOST,
        port=PORT,
        reload=True,
        workers=1,
    )
