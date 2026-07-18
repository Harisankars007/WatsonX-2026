import os
from pathlib import Path
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# MeetBot Configuration
# Loads secrets from .env file automatically
# ─────────────────────────────────────────────

# Load .env from the meetbot directory
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)


# Google Meet
MEET_URL         = os.environ.get("MEET_URL", "https://meet.google.com/aty-hpzp-apn")
BOT_DISPLAY_NAME = "MeetBot 🤖"
BOT_EMAIL        = os.environ.get("BOT_EMAIL", "")
BOT_PASSWORD     = os.environ.get("BOT_PASSWORD", "")

# IBM Speech to Text
STT_API_KEY  = os.environ.get("STT_API_KEY", "")
STT_URL      = os.environ.get("STT_URL", "https://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/5bd28040-fe19-422b-8d5e-14b2f6ad3c0b/v1/recognize")
STT_WS_URL   = os.environ.get("STT_WS_URL", "wss://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/5bd28040-fe19-422b-8d5e-14b2f6ad3c0b/v1/recognize")

# IBM watsonx.ai
WATSONX_API_KEY = os.environ.get("WATSONX_API_KEY", "")
WATSONX_URL     = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
WATSONX_PROJECT = os.environ.get("WATSONX_PROJECT", "")
WATSONX_MODEL   = "meta-llama/llama-3-3-70b-instruct"

# Audio
# BlackHole 2ch native rate is 48000 Hz — must match or PyAudio will resample
# silently and IBM STT needs 16kHz, so we capture at 48k and tell STT 16k via
# the downsample factor (handled in audio_capture.py).
AUDIO_SAMPLE_RATE    = 48000   # native BlackHole rate
AUDIO_STT_RATE       = 16000   # what IBM STT expects
AUDIO_CHANNELS       = 1
AUDIO_CHUNK_SIZE     = 4096
VIRTUAL_AUDIO_DEVICE = "BlackHole 2ch"

# Wake word
WAKE_WORD = "hey meetbot"

# Output
OUTPUT_JSON = "meeting_results.json"
