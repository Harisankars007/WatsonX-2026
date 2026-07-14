"""
Phase 3: Wake word detection and command parsing.
Detects "Hey MeetBot" in live transcript and extracts the command.
"""

import logging
from config import WAKE_WORD

log = logging.getLogger("MeetBot.WakeWord")


COMMAND_MAP = {
    "note this"       : "note",
    "note:"           : "note",
    "action item"     : "action_item",
    "action items"    : "list_actions",
    "summarize"       : "summarize",
    "summary"         : "summarize",
    "who owns"        : "query",
    "what did"        : "query",
    "end meeting"     : "end_meeting",
    "end the meeting" : "end_meeting",
}


def detect_wake_word(text: str) -> tuple[bool, str, str]:
    """
    Check if text contains wake word.

    Returns:
        (triggered, command_type, command_payload)
    """
    lower = text.lower().strip()

    if WAKE_WORD not in lower:
        return False, "", ""

    # Extract everything after the wake word
    after_wake = lower.split(WAKE_WORD, 1)[-1].strip()
    after_wake = after_wake.lstrip(",:- ")

    log.info(f"🔔 Wake word detected! Command: '{after_wake}'")

    # Match command type
    for keyword, cmd_type in COMMAND_MAP.items():
        if keyword in after_wake:
            # Extract payload after the keyword
            payload = after_wake.split(keyword, 1)[-1].strip().lstrip(",:- ")
            return True, cmd_type, payload

    # Generic query if no keyword matched
    return True, "query", after_wake


def format_bot_response(command_type: str, result: str) -> str:
    """Format the bot's response for Meet chat."""
    prefix = {
        "note"        : "📌 Note saved",
        "action_item" : "✅ Action item added",
        "list_actions": "📋 Action Items so far",
        "summarize"   : "📝 Summary",
        "query"       : "🤖 MeetBot",
        "end_meeting" : "📊 Meeting Report Ready",
    }.get(command_type, "🤖 MeetBot")

    return f"{prefix}:\n{result}"
