# 🤖 MeetBot — AI Meeting Assistant for Google Meet

MeetBot joins your Google Meet as a participant, transcribes everything live using IBM Speech to Text, detects voice commands via wake word **"Hey MeetBot"**, and generates a structured meeting report powered by **watsonx.ai**.

---

## Features

- 🎬 **Joins Google Meet** automatically as a participant
- 🎙️ **Live transcription** with IBM Speech to Text (speaker labels + timestamps)
- 🔔 **Wake word detection** — say *"Hey MeetBot"* to trigger commands
- 💬 **Replies in Meet chat** with answers, summaries, and action items
- 📊 **Final JSON report** — summary, action items, key decisions, speaker mapping

---

## Voice Commands

| Say | What happens |
|---|---|
| `Hey MeetBot, note this: [text]` | Saves a manual note |
| `Hey MeetBot, action item: [task]` | Logs an action item |
| `Hey MeetBot, what are the action items?` | Posts all action items in chat |
| `Hey MeetBot, summarize` | Posts a mini-summary in chat |
| `Hey MeetBot, who owns [task]?` | Answers from transcript context |
| `Hey MeetBot, end meeting` | Generates final report and leaves |

---

## Setup

### 1. Install system dependencies
```bash
# macOS — virtual audio device
brew install blackhole-2ch

# Chrome driver
brew install chromedriver
```

### 2. Install Python packages
```bash
pip install -r requirements.txt
```

### 3. Configure credentials
Edit `config.py`:
```python
MEET_URL         = "https://meet.google.com/xxx-xxxx-xxx"
BOT_EMAIL        = "your-bot-account@gmail.com"
BOT_PASSWORD     = "your-password"
STT_API_KEY      = "..."
WATSONX_API_KEY  = "..."
```

### 4. Set up BlackHole (macOS)
1. Open **Audio MIDI Setup** → Create **Multi-Output Device**
2. Include **BlackHole 2ch** + your speakers
3. Set it as your default output in System Settings → Sound

---

## Run

```bash
cd meetbot
python bot.py --url "https://meet.google.com/xxx-xxxx-xxx"
```

### Options
```
--url         Google Meet URL
--no-login    Skip Google login (join as guest)
--no-browser  Audio-only mode (no browser)
```

---

## Output — `meeting_results.json`

```json
{
  "metadata": { "meeting_start": "...", "duration_mins": 45 },
  "transcript": { "full": "...", "segments": [...] },
  "manual_notes": [{ "time": "05:32", "note": "..." }],
  "action_items": [{ "item": "...", "owner": "...", "time": "..." }],
  "analysis": {
    "summary": "...",
    "action_items": [...],
    "key_decisions": [...],
    "speaker_mapping": {}
  }
}
```

---

## Architecture

```
Google Meet (Chrome/Selenium)
        ↓ audio
BlackHole (virtual audio device)
        ↓ PCM stream
IBM Speech to Text (WebSocket)
        ↓ live transcript
Wake Word Detector ("Hey MeetBot")
        ↓ command
watsonx.ai (Llama 3.3 70B)
        ↓ response
Google Meet Chat (Selenium)
        ↓
meeting_results.json
```
