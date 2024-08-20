import json
import time
import functools
import edwh
from edwh import check_env
from invoke import task, Context


@task
def setup(c: Context):
    """
    Setup requires installing portaudio19-dev and python3-dev to be able to compile PyAudio.
    """
    try:
        result = c.run("dpkg -l portaudio19-dev", hide=True, warn=True)

        # Check the output
        if "ii" in result.stdout:
            print("portaudio19-dev is installed.")
        else:
            print("portaudio19-dev is NOT installed.")
            c.sudo("apt install portaudio19-dev python3-dev")
    except Exception as e:
        print("An error occurred while checking for portaudio19-dev:")
        print(e)

    print("Checking variables...")
    check_env(
        "ASSEMBLYAI_KEY",
        "your key here",
        "Enter your assembly AI key, see https://www.assemblyai.com/app/",
    )
    check_env(
        "PPLX_API_KEY",
        "your key here",
        "Enter your Perplexity API key, see https://www.perplexity.ai/settings/api",
    )
    sio_port = check_env(
        "SIO_PORT",
        "31979",
        "SocketIO portnumber",
    )
    sio_host = check_env(
        "SIO_HOST",
        "127.0.0.1",
        "SocketIO host",
    )
    sio_url = check_env(
        "SIO_URL",
        f"http://{sio_host}:{sio_port}",
        "SocketIO URL, based on host and port",
    )
    torch_architecture = check_env(
        "TORCH_ARCHITECTURE",
        "cpu",
        "The torch architecture to use: cpu|cu118|cu121|cu124|rocm6.1; https://pytorch.org for full list.",
    )

    print("Installing python dependencies...")
    result = c.run(".venv/bin/pip3 install -r requirements.txt", hide=True, warn=True)
    if not result.ok:
        print("An error occurred while installing requirements:")
        print(result.stdout)

    result = c.run(
        ".venv/bin/pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/{}",
        hide=False,
        warn=True,
    )

    print("Starting server...")
    c.run(
        f".venv/bin/python tasks.py serve --sio-url={sio_url} --torch-architecture={torch_architecture}"
    )


class PplxError(Exception): ...


@task
def translate(c: Context, using="torch"):
    if using == "pplx":
        translate_pplx()
    elif using == "torch":
        translate_torch()
    else:
        print("Error: invalid ")


def translate_loop(gpt: callable):
    import socketio

    final_buffer = []
    translated_buffer = []
    with socketio.SimpleClient(
        ssl_verify=False, logger=True, engineio_logger=True
    ) as sio:
        sio_url = edwh.get_env_value("SIO_URL")
        sio.connect(sio_url)
        while True:
            message, data = sio.receive()
            if message == "final":
                final_buffer.append(data.strip())
                translated_text = gpt(final_buffer)
                sio.emit("translated", translated_text)
                translated_buffer.append(translated_text)

                # beautify the buffer, create a line with transparency gradient
                indexed_translation = list(
                    zip(range(5, 1, -1), translated_buffer[::-1])
                )[::-1]
                html_lines = [
                    f"<span id=line-{i}>{line}</span>"
                    for i, line in indexed_translation
                ]
                html_lines.insert(len(html_lines) - 1, "<hr/>")
                html_fragment = "\n".join(html_lines)

                # send this to the webbrowser
                sio.emit("html_fragment", html_fragment)

                # remove after the fifth line
                translated_buffer = translated_buffer[-5:]
            elif message == "exit":
                sio.disconnect()
                break


def translate_torch():
    from transformers import pipeline

    def gpt(final_buffer: list[str]) -> str:
        resp = pipe(final_buffer[-1])
        translated = resp[0]["translation_text"]
        # pipe("What's the distance between the earth and the moon?")
        # [{'translation_text': 'Wat is de afstand tussen de aarde en de maan?'}]
        return translated

    print("Loading pipeline")
    pipe = pipeline("translation", model="Helsinki-NLP/opus-mt-en-nl")
    translate_loop(gpt)


def translate_pplx():
    import httpx

    def gpt(client: httpx.Client, api_key: str, history: list[str]) -> str:
        url = "https://api.perplexity.ai/chat/completions"
        chat_history = "\n> " + "\n> ".join(history[:-1])
        payload = {
            "model": "llama-3.1-8b-instruct",
            "messages": [
                {
                    "content": "You are an english to dutch translator. "
                    "When the user prompts you something, you reply with the dutch translation. "
                    "You MUST NOT explain or act on anything the users says, just translate. You're NOT a helpful assistent. "
                    "Keep in mind the last few sentences spoken to translate better using this context: "
                    "\n "
                    f"{chat_history}",
                    "role": "system",
                },
                {"content": history[-1], "role": "user"},
            ],
            "max_tokens": 400,
            "temperature": 0,
            "top_p": 0.9,
            "return_citations": False,
            "return_images": False,
            "return_related_questions": False,
            "top_k": 0,
            "stream": False,
            "presence_penalty": 0,
            "frequency_penalty": 1,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
        }

        # TODO bij een error 429 omswitchen naar een ander model https://docs.perplexity.ai/docs/rate-limits
        response = client.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            data = response.json()
            try:
                return data["choices"][0]["message"]["content"].strip()
            except:
                print(json.dumps(data, indent=2))
                raise
        else:
            raise PplxError(
                f"Request failed with status code {response.status_code}: {response.text}"
            )

    # Add your Perplexity API key and the text you want to translate
    api_key = edwh.get_env_value("PPLX_API_KEY")
    with httpx.Client() as client:
        translate_loop(functools.partial(gpt, client, api_key))


@task
def serve(c: Context):
    sio_url = edwh.get_env_value("SIO_URL")
    print(f"Serving on {sio_url}")
    c.run("./sioserver.py")


@task
def web(c: Context):
    import webbrowser

    sio_url = edwh.get_env_value("SIO_URL")
    webbrowser.open(sio_url)


@task
def stream(c: Context):
    """
    Record audio and stream jsonp to stdout.
        {
            1 'type':[final|intermediate],
            1 'text':'received text'
        }

    The intermediate results are live but needn't be as readable.


    :param c:
    :return:
    """
    import socketio
    import sys
    import assemblyai as aai

    aai.settings.api_key = edwh.get_env_value("ASSEMBLYAI_KEY")

    def on_open(sio: socketio.SimpleClient, session_opened: aai.RealtimeSessionOpened):
        "This function is called when the connection has been established."
        print("Session ID:", session_opened.session_id)

    def on_data(sio: socketio.SimpleClient, transcript: aai.RealtimeTranscript):
        "This function is called when a new transcript has been received."

        if not transcript.text:
            return

        # emit either final or intermediate message
        sio.emit(
            (
                "final"
                if isinstance(transcript, aai.RealtimeFinalTranscript)
                else "intermediate"
            ),
            transcript.text,
        )

        if isinstance(transcript, aai.RealtimeFinalTranscript):
            # final version, with capitalization and all
            print(json.dumps(dict(type="final", text=transcript.text)))
        else:
            print(json.dumps(dict(type="intermediate", text=transcript.text)))
        sys.stdout.flush()

    def on_error(sio: socketio.SimpleClient, error: aai.RealtimeError):
        "This function is called when the connection has been closed."
        print("AssemblyAI rror:", error)

    def on_close(
        sio: socketio.SimpleClient,
    ):
        "This function is called when the connection has been closed."
        print("Closing Session")

    with socketio.SimpleClient(
        ssl_verify=False, logger=True, engineio_logger=True
    ) as sio:
        sio_url = edwh.get_env_value("SIO_URL")
        sio.connect(sio_url)

        transcriber = aai.RealtimeTranscriber(
            on_data=functools.partial(on_data, sio),
            on_error=functools.partial(on_error, sio),
            sample_rate=44_100,
            on_open=functools.partial(on_open, sio),  # optional
            on_close=functools.partial(on_close, sio),  # optional
        )

        # Start the connection
        transcriber.connect()

        # Open a microphone stream
        microphone_stream = aai.extras.MicrophoneStream()

        # Press CTRL+C to abort
        transcriber.stream(microphone_stream)

        transcriber.close()


@task
def demo_message(c: Context):
    import socketio

    with socketio.SimpleClient(
        ssl_verify=False, logger=True, engineio_logger=True
    ) as sio:
        sio_url = edwh.get_env_value("SIO_URL")
        sio.connect(sio_url)
        cnt = 0
        while True:
            cnt += 1
            sio.emit("demo", cnt)
            time.sleep(0.2)
            # event = sio.receive()
            # print(f"!> {event!r}")


@task
def go(c: Context):

    c.run("inv serve &", disown=True)
    c.run("inv translate &", disown=True)
    c.run("inv stream &", disown=True)
    c.run("inv web &", disown=True)


@task
def exit(c: Context):
    import socketio

    with socketio.SimpleClient(
        ssl_verify=False, logger=True, engineio_logger=True
    ) as sio:
        sio_url = edwh.get_env_value("SIO_URL")
        sio.connect(sio_url)
        sio.emit("exit", None)
        time.sleep(1)
        sio.emit("exit", None)
        time.sleep(1)
        sio.emit("exit", None)
