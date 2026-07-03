import os
import json
import subprocess
import requests
from datetime import datetime
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as Params

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
INPUT_FILE       = "/Users/harisankars/Documents/watson.mp4"  # video or audio file
STT_API_KEY      = "nbgt7zi8mY6sTodHoaLPG_UILpS6b8sSySHQ9nONvY3k"
STT_URL          = "https://api.us-south.speech-to-text.watson.cloud.ibm.com/instances/5bd28040-fe19-422b-8d5e-14b2f6ad3c0b/v1/recognize"
WATSONX_API_KEY  = "qpZXdOS0iy-bGzj1bZ5BLhulyiunXQEcHgUdXMn1NSaI"
WATSONX_URL      = "https://us-south.ml.cloud.ibm.com"
WATSONX_PROJECT  = "744c52f3-4061-4e40-ac2a-a7fd69f7266d"
OUTPUT_JSON      = "meeting_results.json"

# ─────────────────────────────────────────────
# STEP 1: Convert video to audio (if needed)
# ─────────────────────────────────────────────
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v"}

_, ext = os.path.splitext(INPUT_FILE)
audio_file = INPUT_FILE  # default: already an audio file
converted = False

if ext.lower() in VIDEO_EXTENSIONS:
    print(f"🎬 Video detected ({ext}). Converting to FLAC audio...")
    audio_file = INPUT_FILE.rsplit(".", 1)[0] + "_converted.flac"

    result = subprocess.run(
        ["ffmpeg", "-y", "-i", INPUT_FILE, "-vn", "-ac", "1", "-ar", "16000", audio_file],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("❌ ffmpeg conversion failed:")
        print(result.stderr)
        exit(1)

    converted = True
    print(f"✅ Audio extracted: {audio_file}")
else:
    print(f"🎵 Audio file detected ({ext}). Skipping conversion.")

# ─────────────────────────────────────────────
# STEP 2: Speech to Text — Transcribe audio
# ─────────────────────────────────────────────
print("\n🎙️  Transcribing audio with IBM Speech to Text...")

MAX_RETRIES = 3
stt_result = None

for attempt in range(1, MAX_RETRIES + 1):
    try:
        print(f"  Attempt {attempt}/{MAX_RETRIES}...")
        with open(audio_file, "rb") as audio:
            stt_response = requests.post(
                STT_URL,
                auth=("apikey", STT_API_KEY),
                headers={"Content-Type": "audio/flac"},
                params={
                    "speaker_labels": "true",
                    "timestamps": "true",
                    "max_alternatives": 3
                },
                data=audio,
                timeout=300  # 5 minutes for large files
            )
        stt_response.raise_for_status()
        stt_result = stt_response.json()
        print("  ✅ Transcription successful.")
        break
    except (requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
        print(f"  ⚠️  Attempt {attempt} failed: {e}")
        if attempt == MAX_RETRIES:
            print("❌ All retries exhausted. Exiting.")
            exit(1)


# Extract best transcript and all alternatives
transcript_lines = []
all_alternatives = []
timestamps = []

for result in stt_result.get("results", []):
    alternatives = result.get("alternatives", [])
    if alternatives:
        transcript_lines.append(alternatives[0].get("transcript", "").strip())
        all_alternatives.append([a.get("transcript", "").strip() for a in alternatives])
        timestamps.extend(alternatives[0].get("timestamps", []))

transcript = " ".join(transcript_lines)
print("\n📝 Raw Transcript:\n")
print(transcript)

# Build speaker labels list
speaker_labels = [
    {
        "from": label.get("from"),
        "to": label.get("to"),
        "speaker": label.get("speaker"),
        "confidence": label.get("confidence")
    }
    for label in stt_result.get("speaker_labels", [])
]

# ─────────────────────────────────────────────
# STEP 3: watsonx.ai — Analyze transcript
# ─────────────────────────────────────────────
print("\n🤖 Analyzing transcript with watsonx.ai...\n")

credentials = Credentials(
    api_key=WATSONX_API_KEY,
    url=WATSONX_URL
)

model = ModelInference(
    model_id="meta-llama/llama-3-3-70b-instruct",
    credentials=credentials,
    project_id=WATSONX_PROJECT,
    params={
        Params.MAX_NEW_TOKENS: 1024
    }
)

messages = [
    {
        "role": "system",
        "content": "You are an AI meeting assistant. Analyze meeting transcripts and provide structured JSON output only. No extra text."
    },
    {
        "role": "user",
        "content": f"""Below is a meeting transcript generated from audio using IBM Speech to Text.

Transcript:
{transcript}

Respond ONLY with a valid JSON object in this exact format:
{{
  "summary": "...",
  "action_items": [
    {{"item": "...", "owner": "...", "due": "..."}}
  ],
  "key_decisions": ["...", "..."],
  "speaker_mapping": {{
    "Speaker 0": "...",
    "Speaker 1": "..."
  }}
}}"""
    }
]

response = model.chat(messages=messages)
analysis_text = response["choices"][0]["message"]["content"].strip()

# Parse watsonx JSON response
try:
    # Strip markdown code fences if present
    if analysis_text.startswith("```"):
        analysis_text = analysis_text.split("```")[1]
        if analysis_text.startswith("json"):
            analysis_text = analysis_text[4:]
    analysis_json = json.loads(analysis_text)
except json.JSONDecodeError:
    # Fallback: store raw text if not valid JSON
    analysis_json = {"raw_analysis": analysis_text}

# ─────────────────────────────────────────────
# STEP 4: Combine all results into JSON
# ─────────────────────────────────────────────
output = {
    "metadata": {
        "input_file": INPUT_FILE,
        "audio_file": audio_file,
        "video_converted": converted,
        "processed_at": datetime.now().isoformat()
    },
    "transcription": {
        "transcript": transcript,
        "alternatives": all_alternatives,
        "timestamps": timestamps,
        "speaker_labels": speaker_labels,
        "raw_stt_response": stt_result
    },
    "analysis": analysis_json
}

# Save to JSON file
with open(OUTPUT_JSON, "w") as f:
    json.dump(output, f, indent=2)

print("📊 Meeting Analysis:\n")
print(json.dumps(analysis_json, indent=2))
print(f"\n✅ Full results saved to: {OUTPUT_JSON}")
