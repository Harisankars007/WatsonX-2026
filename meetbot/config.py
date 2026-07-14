# ─────────────────────────────────────────────
# MeetBot Configuration
# ─────────────────────────────────────────────

# Google Meet
MEET_URL        = "https://meet.google.com/xxx-xxxx-xxx"  # ← replace with your Meet link
BOT_DISPLAY_NAME = "MeetBot 🤖"
BOT_EMAIL       = "your-bot-google-account@gmail.com"     # ← replace with bot Google account
BOT_PASSWORD    = "your-bot-password"                     # ← replace

# IBM Speech to Text
STT_API_KEY     = "nbgt7zi8mY6sTodHoaLPG_UILpS6b8sSySHQ9nONvY3k"
STT_URL         = "https://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/5bd28040-fe19-422b-8d5e-14b2f6ad3c0b/v1/recognize"
STT_WS_URL      = "wss://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/5bd28040-fe19-422b-8d5e-14b2f6ad3c0b/v1/recognize"

# IBM watsonx.ai
WATSONX_API_KEY = "qpZXdOS0iy-bGzj1bZ5BLhulyiunXQEcHgUdXMn1NSaI"
WATSONX_URL     = "https://us-south.ml.cloud.ibm.com"
WATSONX_PROJECT = "744c52f3-4061-4e40-ac2a-a7fd69f7266d"
WATSONX_MODEL   = "meta-llama/llama-3-3-70b-instruct"

# Audio
AUDIO_SAMPLE_RATE   = 16000
AUDIO_CHANNELS      = 1
AUDIO_CHUNK_SIZE    = 4096
VIRTUAL_AUDIO_DEVICE = "BlackHole 2ch"  # macOS virtual audio device

# Wake word
WAKE_WORD = "hey meetbot"

# Output
OUTPUT_JSON = "meeting_results.json"
