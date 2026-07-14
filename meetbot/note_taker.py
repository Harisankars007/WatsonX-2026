"""
Maintains the live transcript, manual notes, action items,
and generates the final JSON report.
"""

import json
import logging
from datetime import datetime
from config import OUTPUT_JSON

log = logging.getLogger("MeetBot.NoteTaker")


class NoteTaker:
    def __init__(self):
        self.transcript_segments = []   # list of {time, speaker, text, final}
        self.manual_notes        = []   # list of {time, note}
        self.action_items        = []   # list of {time, item, owner}
        self.start_time          = datetime.now()

    # ── Transcript ────────────────────────────────────────────────

    def add_transcript(self, text: str, is_final: bool, speaker: str = "Unknown"):
        ts = self._elapsed()
        entry = {"time": ts, "speaker": speaker, "text": text, "final": is_final}
        self.transcript_segments.append(entry)
        status = "✅" if is_final else "…"
        log.info(f"[{ts}] {status} {speaker}: {text}")

    def get_full_transcript(self) -> str:
        """Return only finalized transcript segments as a single string."""
        lines = [
            f"[{s['time']}] {s['speaker']}: {s['text']}"
            for s in self.transcript_segments if s["final"]
        ]
        return "\n".join(lines)

    def get_raw_transcript(self) -> str:
        """Return plain text of final transcripts (no timestamps/speakers)."""
        return " ".join(
            s["text"] for s in self.transcript_segments if s["final"]
        )

    # ── Manual notes ──────────────────────────────────────────────

    def add_note(self, note: str):
        ts = self._elapsed()
        self.manual_notes.append({"time": ts, "note": note})
        log.info(f"📌 Note [{ts}]: {note}")

    def add_action_item(self, item: str, owner: str = ""):
        ts = self._elapsed()
        self.action_items.append({"time": ts, "item": item, "owner": owner})
        log.info(f"✅ Action Item [{ts}]: {item} — Owner: {owner or 'TBD'}")

    def get_manual_notes_list(self) -> list:
        return [n["note"] for n in self.manual_notes]

    # ── Final report ──────────────────────────────────────────────

    def save_report(self, analysis: dict, stt_raw: dict = None):
        """Save complete meeting report to JSON file."""
        report = {
            "metadata": {
                "meeting_start": self.start_time.isoformat(),
                "meeting_end":   datetime.now().isoformat(),
                "duration_mins": round(
                    (datetime.now() - self.start_time).seconds / 60, 1
                )
            },
            "transcript": {
                "full":     self.get_full_transcript(),
                "segments": self.transcript_segments,
                "raw_stt":  stt_raw or {}
            },
            "manual_notes": self.manual_notes,
            "action_items": self.action_items,
            "analysis":     analysis
        }

        with open(OUTPUT_JSON, "w") as f:
            json.dump(report, f, indent=2)

        log.info(f"✅ Meeting report saved to: {OUTPUT_JSON}")
        return report

    # ── Helpers ───────────────────────────────────────────────────

    def _elapsed(self) -> str:
        delta = datetime.now() - self.start_time
        mins  = delta.seconds // 60
        secs  = delta.seconds % 60
        return f"{mins:02d}:{secs:02d}"
