"""
MeetBot — Main orchestrator.
Joins Google Meet, transcribes live, detects wake word,
responds to commands, and saves the final meeting report.

Usage:
    python bot.py --url "https://meet.google.com/xxx-xxxx-xxx"
"""

import time
import signal
import logging
import argparse

from join_meet   import get_driver, login_google, join_meeting, send_chat_message, leave_meeting
from audio_capture import LiveTranscriber
from wake_word   import detect_wake_word, format_bot_response
from ai_engine   import AIEngine
from note_taker  import NoteTaker
from config      import MEET_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("MeetBot")

# ── Global state ──────────────────────────────────────────────────
driver      = None
transcriber = None
running     = True


def handle_shutdown(sig, frame):
    """Handle Ctrl+C gracefully."""
    global running
    log.info("🛑 Shutdown signal received. Wrapping up...")
    running = False


signal.signal(signal.SIGINT, handle_shutdown)


# ── Transcript callback ───────────────────────────────────────────

def on_transcript(note_taker: NoteTaker, ai: AIEngine, text: str, is_final: bool):
    """Called every time IBM STT returns a transcript segment."""
    note_taker.add_transcript(text, is_final)

    if not is_final:
        return  # Only act on finalized segments

    # ── Check for wake word ──────────────────────────────────────
    triggered, cmd_type, payload = detect_wake_word(text)

    if not triggered:
        return

    log.info(f"🔔 Command: {cmd_type} | Payload: {payload}")
    transcript = note_taker.get_raw_transcript()

    # ── Handle each command ──────────────────────────────────────
    response = ""

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

    # ── Post to Meet chat ─────────────────────────────────────────
    if driver and response:
        chat_msg = format_bot_response(cmd_type, response)
        send_chat_message(driver, chat_msg)


# ── Main ──────────────────────────────────────────────────────────

def main():
    global driver, transcriber, running

    parser = argparse.ArgumentParser(description="MeetBot — AI meeting assistant")
    parser.add_argument("--url",        default=MEET_URL,  help="Google Meet URL")
    parser.add_argument("--no-login",   action="store_true", help="Skip Google login (guest join)")
    parser.add_argument("--no-browser", action="store_true", help="Skip browser (audio-only mode)")
    args = parser.parse_args()

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
            log.error("Failed to join meeting. Exiting.")
            driver.quit()
            return

        send_chat_message(driver,
            "👋 Hi everyone! I'm MeetBot 🤖\n"
            "I'll be transcribing this meeting and taking notes.\n"
            "Say 'Hey MeetBot' to give me a command!\n"
            "Examples:\n"
            "• 'Hey MeetBot, note this: ...'\n"
            "• 'Hey MeetBot, summarize'\n"
            "• 'Hey MeetBot, what are the action items?'\n"
            "• 'Hey MeetBot, end meeting'"
        )

    # ── Phase 2 & 3: Live transcription + wake word ──────────────
    log.info("🎙️ Starting live transcription...")

    transcriber = LiveTranscriber(
        on_transcript=lambda text, is_final: on_transcript(note_taker, ai, text, is_final)
    )
    transcriber.start()

    log.info("✅ MeetBot is live! Listening for 'Hey MeetBot'...")

    # ── Keep running until shutdown ──────────────────────────────
    while running:
        time.sleep(1)

    # ── Phase 5: End of meeting ───────────────────────────────────
    log.info("📊 Generating final meeting report...")
    transcriber.stop()

    full_transcript = note_taker.get_raw_transcript()
    analysis        = ai.generate_final_report(full_transcript, note_taker.get_manual_notes_list())
    report          = note_taker.save_report(analysis)

    # Print summary to terminal
    import json
    print("\n" + "="*60)
    print("📊 MEETING REPORT")
    print("="*60)
    print(json.dumps(report["analysis"], indent=2))
    print(f"\n✅ Full report saved to: meeting_results.json")

    # Post final summary to chat
    if driver:
        summary = report["analysis"].get("summary", "Meeting ended.")
        send_chat_message(driver, f"📊 Meeting Summary:\n{summary}\n\nFull report saved!")
        leave_meeting(driver)


if __name__ == "__main__":
    main()
