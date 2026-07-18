"""
MeetBot — Main orchestrator.
Joins Google Meet, transcribes live, detects wake word,
responds to commands, and saves the final meeting report.

Usage:
    python bot.py --url "https://meet.google.com/xxx-xxxx-xxx"
"""

import os
import sys
import time
import signal
import logging
import argparse
import json
import threading

from join_meet      import get_driver, login_google, join_meeting, send_chat_message, leave_meeting
from audio_capture  import LiveTranscriber
from wake_word      import detect_wake_word, format_bot_response
from ai_engine      import AIEngine
from note_taker     import NoteTaker
from config         import MEET_URL

# ── Logging setup ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                        # terminal
        logging.FileHandler("meetbot_run.log", "w")    # file
    ]
)
log = logging.getLogger("MeetBot")

# ── PID lock file — prevents duplicate instances ──────────────────
_PID_FILE = os.path.join(os.path.dirname(__file__), "meetbot.pid")

def _acquire_pid_lock():
    """Write our PID to the lock file. Exit if another instance is running."""
    if os.path.exists(_PID_FILE):
        old_pid = None
        try:
            with open(_PID_FILE) as f:
                old_pid = int(f.read().strip())
            # Check if that process is actually alive
            os.kill(old_pid, 0)
            log.error(
                f"❌ MeetBot is already running (PID {old_pid}). "
                f"Stop it first or delete {_PID_FILE} if it is stale."
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            # Stale PID file — previous run crashed or was suspended without cleanup
            log.warning(f"⚠️  Stale PID file found (PID {old_pid}) — removing it.")
            os.remove(_PID_FILE)

    with open(_PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def _release_pid_lock():
    try:
        os.remove(_PID_FILE)
    except FileNotFoundError:
        pass

# ── Global state ──────────────────────────────────────────────────
driver      = None
transcriber = None
running     = True


def handle_shutdown(sig, frame):
    """Handle termination signals — wrap up and save report."""
    global running
    sig_name = {signal.SIGINT: "Ctrl+C", signal.SIGTERM: "SIGTERM"}.get(sig, sig)
    log.info(f"🛑 {sig_name} received — wrapping up meeting...")
    running = False

# Catch Ctrl+C, kill, and system shutdown
signal.signal(signal.SIGINT,  handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# Ignore Ctrl+Z — suspending a live bot mid-session causes exactly the
# "still recording after logout" problem. Force the user to Ctrl+C instead.
signal.signal(signal.SIGTSTP, signal.SIG_IGN)


# ── Transcript callback ───────────────────────────────────────────

def on_transcript(note_taker: NoteTaker, ai: AIEngine, text: str, is_final: bool):
    """Called every time IBM STT returns a transcript segment."""
    note_taker.add_transcript(text, is_final)

    if not is_final:
        # Show interim results in terminal
        print(f"\r💬 {text}", end="", flush=True)
        return

    print()  # newline after final transcript
    log.info(f"📝 [{note_taker._elapsed()}] {text}")

    # ── Check for wake word ──────────────────────────────────────
    triggered, cmd_type, payload = detect_wake_word(text)
    if not triggered:
        return

    log.info(f"🔔 Wake word! Command: {cmd_type} | Payload: {payload}")
    transcript = note_taker.get_raw_transcript()
    response   = ""

    if cmd_type == "note":
        note_taker.add_note(payload)
        response = f"Got it! Note saved: '{payload}'"

    elif cmd_type == "action_item":
        result = ai.handle_action_item(payload, transcript)
        note_taker.add_action_item(result)
        response = result

    elif cmd_type == "list_actions":
        response = ai.handle_list_actions(transcript, note_taker.get_manual_notes_list())

    elif cmd_type == "summarize":
        response = ai.handle_summarize(transcript)

    elif cmd_type == "query":
        response = ai.handle_query(payload, transcript)

    elif cmd_type == "end_meeting":
        global running
        running = False
        response = "Wrapping up! Generating meeting report... 📊"

    # Post response to Meet chat
    if driver and response:
        threading.Thread(
            target=send_chat_message,
            args=(driver, format_bot_response(cmd_type, response)),
            daemon=True
        ).start()


# ── Save final report ─────────────────────────────────────────────

def save_report(note_taker: NoteTaker, ai: AIEngine):
    """Generate and save the final meeting JSON report."""
    log.info("📊 Generating final meeting report...")

    full_transcript = note_taker.get_raw_transcript()

    if not full_transcript.strip():
        log.warning("⚠️ Transcript is empty — saving basic report.")
        analysis = {
            "summary": "No transcript captured.",
            "action_items": [],
            "key_decisions": [],
            "speaker_mapping": {},
            "manual_notes": note_taker.get_manual_notes_list()
        }
    else:
        analysis = ai.generate_final_report(
            full_transcript,
            note_taker.get_manual_notes_list()
        )

    report = note_taker.save_report(analysis)

    print("\n" + "="*60)
    print("📊 MEETING REPORT")
    print("="*60)
    print(json.dumps(report["analysis"], indent=2))
    print(f"\n✅ Full report saved to: meeting_results.json")
    print(f"✅ Run log saved to:     meetbot_run.log")

    return report


# ── Main ──────────────────────────────────────────────────────────

def main():
    global driver, transcriber, running

    # ── Prevent duplicate instances ──────────────────────────────
    _acquire_pid_lock()

    parser = argparse.ArgumentParser(description="MeetBot — AI meeting assistant")
    parser.add_argument("--url",        default=MEET_URL,    help="Google Meet URL")
    parser.add_argument("--no-login",   action="store_true", help="Skip Google login (guest join)")
    parser.add_argument("--no-browser", action="store_true", help="Skip browser (audio-only mode)")
    args = parser.parse_args()

    try:
        note_taker = NoteTaker()
        ai         = AIEngine()

        # ── Phase 1: Join meeting ────────────────────────────────────
        if not args.no_browser:
            log.info("🚀 Starting MeetBot...")
            driver = get_driver()

            if not args.no_login:
                login_google(driver)

            joined = join_meeting(driver, args.url)
            if not joined:
                log.error("❌ Failed to join meeting. Exiting.")
                driver.quit()
                return

            log.info("✅ Successfully joined the meeting!")

        # ── Phase 2: Start live transcription ────────────────────────
        log.info("🎙️ Starting live audio capture & transcription...")

        transcriber = LiveTranscriber(
            on_transcript=lambda text, is_final: on_transcript(note_taker, ai, text, is_final)
        )
        transcriber.start()

        log.info("✅ MeetBot is live! Say 'Hey MeetBot' to give a command.")
        log.info("   Press Ctrl+C at any time to end the meeting and save report.")

        # ── Phase 3: Send welcome message in background ──────────────
        if not args.no_browser and driver:
            def _send_welcome():
                time.sleep(3)
                send_chat_message(driver,
                    "👋 Hi everyone! I'm MeetBot 🤖\n"
                    "I'm transcribing this meeting live.\n"
                    "Say 'Hey MeetBot' to give me a command:\n"
                    "• 'Hey MeetBot, note this: ...'\n"
                    "• 'Hey MeetBot, summarize'\n"
                    "• 'Hey MeetBot, action items?'\n"
                    "• 'Hey MeetBot, end meeting'"
                )
            threading.Thread(target=_send_welcome, daemon=True).start()

        # ── Phase 4: Keep running — heartbeat log every 60s ──────────
        elapsed = 0
        while running:
            time.sleep(1)
            elapsed += 1
            if elapsed % 60 == 0:
                mins = elapsed // 60
                segments = sum(1 for s in note_taker.transcript_segments if s["final"])
                log.info(f"⏱️  Running {mins} min | {segments} transcript segments captured")

        # ── Phase 5: End of meeting — save report ────────────────────
        transcriber.stop()
        report = save_report(note_taker, ai)

        # Post summary to chat and leave
        if driver:
            summary = report["analysis"].get("summary", "Meeting ended.")
            threading.Thread(
                target=send_chat_message,
                args=(driver, f"📊 Meeting ended!\nSummary: {summary[:200]}"),
                daemon=True
            ).start()
            time.sleep(4)
            leave_meeting(driver)

    finally:
        # Always release the lock so the next run isn't blocked
        _release_pid_lock()
        log.info("🔓 PID lock released.")


if __name__ == "__main__":
    main()
