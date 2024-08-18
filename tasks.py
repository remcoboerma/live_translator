import json
import queue
import time

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

    # try:
    #     result = c.run("dpkg -l python3-pyaudio", hide=True, warn=True)
    #
    #     # Check the output
    #     if "ii" in result.stdout:
    #         print("python3-pyaudio is installed.")
    #     else:
    #         print("python3-pyaudio is NOT installed.")
    #         c.sudo("apt install python3-pyaudio")
    # except Exception as e:
    #     print("An error occurred while checking for python3-pyaudio:")
    #     print(e)
    print("Installing python dependencies...")
    result = c.run(".venv/bin/pip3 install -r requirements.txt", hide=True, warn=True)
    if not result.ok:
        print("An error occurred while installing requirements:")
        print(result.stdout)
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


class PplxError(Exception): ...


@task
def translate(c: Context):
    import httpx

    def gpt(client: httpx.Client, api_key: str, text: str) -> str:
        url = "https://api.perplexity.ai/chat/completions"
        payload = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "content": "You are an english to dutch translator. When the user prompts you something, you reply with the dutch translation.",
                    "role": "system",
                },
                {"content": text, "role": "user"},
            ],
            "max_tokens": 0,
            "temperature": 0.2,
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
    text_to_translate = "Translate this text to dutch: Hi there, i'm a Berliner!"
    import fileinput
    import sys

    with httpx.Client() as client:
        for line in fileinput.input("-"):
            try:
                print(line)
                if line.startswith("final:"):
                    input = line.split("final:")[1].strip()
                    translated_text = gpt(client, api_key, input)
                    print("translated:", translated_text)
            except PplxError as e:
                print("An error occurred:", e)


@task
def serve(c:Context):
    print('Serving on http://127.0.0.1:31979')
    c.run('uvicorn sioserver:app --reload')


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

    import sys
    import assemblyai as aai

    aai.settings.api_key = edwh.get_env_value("ASSEMBLYAI_KEY")

    def translate(transcript: aai.Transcript):
        prompt = "Translate this transcript into Dutch."
        result = transcript.lemur.task(prompt)
        if result.error_message:
            print("Translate errors: ", result.error_message)
        return result.response

    def on_open(session_opened: aai.RealtimeSessionOpened):
        "This function is called when the connection has been established."

        print("Session ID:", session_opened.session_id)

    def on_data(transcript: aai.RealtimeTranscript):
        "This function is called when a new transcript has been received."

        if not transcript.text:
            return

        if isinstance(transcript, aai.RealtimeFinalTranscript):
            # final version, with capitalization and all
            print(json.dumps(dict(type='final', text=transcript.text)))
            # print("final:", transcript.text)
            # print(transcript.text, end="\r\n")
            # print(translate(transcript), end="\r\n")

        else:
            # print("intermediate:", transcript.text)
            print(json.dumps(dict(type='intermediate', text=transcript.text)))
            # in between version, words appends. Will change until Final
            # print(transcript.text, end="\r")
        sys.stdout.flush()

    def on_error(error: aai.RealtimeError):
        "This function is called when the connection has been closed."
        print("AssemblyAI rror:", error)

    def on_close():
        "This function is called when the connection has been closed."
        print("Closing Session")

    transcriber = aai.RealtimeTranscriber(
        on_data=on_data,
        on_error=on_error,
        sample_rate=44_100,
        on_open=on_open,  # optional
        on_close=on_close,  # optional
    )

    # Start the connection
    transcriber.connect()

    # Open a microphone stream
    microphone_stream = aai.extras.MicrophoneStream()

    # Press CTRL+C to abort
    transcriber.stream(microphone_stream)

    transcriber.close()

@task
def demo_final(c:Context):
    import socketio
    with socketio.SimpleClient(ssl_verify=False, logger=True, engineio_logger=True) as sio:
        sio.connect('http://127.0.0.1:31979')
        cnt = 0
        while True:
            cnt += 1
            sio.emit('demo',cnt)
            time.sleep(0.2)
            # event = sio.receive()
            # print(f"!> {event!r}")
