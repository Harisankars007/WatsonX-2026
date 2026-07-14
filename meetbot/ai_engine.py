"""
Phase 4: watsonx.ai engine.
Handles all AI responses — command answers, live Q&A, final meeting analysis.
"""

import logging
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as Params

from config import WATSONX_API_KEY, WATSONX_URL, WATSONX_PROJECT, WATSONX_MODEL

log = logging.getLogger("MeetBot.AI")


class AIEngine:
    def __init__(self):
        credentials = Credentials(
            api_key=WATSONX_API_KEY,
            url=WATSONX_URL
        )
        self.model = ModelInference(
            model_id=WATSONX_MODEL,
            credentials=credentials,
            project_id=WATSONX_PROJECT,
            params={Params.MAX_NEW_TOKENS: 1024}
        )
        log.info("✅ watsonx.ai engine ready.")

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat request to watsonx.ai and return the response text."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt}
        ]
        response = self.model.chat(messages=messages)
        return response["choices"][0]["message"]["content"].strip()

    # ── Command handlers ──────────────────────────────────────────

    def handle_note(self, payload: str) -> str:
        """Save a manual note as-is."""
        return payload if payload else "Note saved (no content detected)."

    def handle_action_item(self, payload: str, transcript: str) -> str:
        """Extract or confirm an action item."""
        prompt = f"""From this meeting context, confirm and format this action item clearly.
Action item mentioned: "{payload}"
Recent transcript: "{transcript[-500:]}"
Format: [Owner if known] - [Task] - [Due date if mentioned]"""
        return self._chat(
            "You are a meeting assistant. Format action items clearly and concisely.",
            prompt
        )

    def handle_list_actions(self, transcript: str, manual_notes: list) -> str:
        """Return all action items identified so far."""
        notes_text = "\n".join(f"- {n}" for n in manual_notes) if manual_notes else "None"
        prompt = f"""From the meeting transcript below, list all action items identified.
Also include these manually noted items: {notes_text}

Transcript:
{transcript[-2000:]}

Return a numbered list of action items with owners if identifiable."""
        return self._chat(
            "You are a meeting assistant. Extract and list all action items.",
            prompt
        )

    def handle_summarize(self, transcript: str, minutes: int = 5) -> str:
        """Summarize the last N minutes of transcript."""
        # Approximate last N minutes using last ~1500 chars
        recent = transcript[-1500:] if len(transcript) > 1500 else transcript
        prompt = f"""Summarize the following meeting transcript section in 3-5 bullet points:

{recent}"""
        return self._chat(
            "You are a meeting assistant. Provide concise bullet-point summaries.",
            prompt
        )

    def handle_query(self, question: str, transcript: str) -> str:
        """Answer a free-form question about the meeting."""
        prompt = f"""Answer this question based on the meeting transcript below.
Question: {question}

Transcript:
{transcript[-2000:]}

If the answer is not in the transcript, say "I couldn't find that in the meeting so far."."""
        return self._chat(
            "You are a meeting assistant. Answer questions based on meeting content only.",
            prompt
        )

    def generate_final_report(self, transcript: str, manual_notes: list) -> dict:
        """Generate the complete end-of-meeting analysis."""
        import json
        notes_text = "\n".join(f"- {n}" for n in manual_notes) if manual_notes else "None"

        prompt = f"""Analyze this complete meeting transcript and manual notes.

Manual notes captured during meeting:
{notes_text}

Full Transcript:
{transcript}

Respond ONLY with a valid JSON object in this exact format:
{{
  "summary": "...",
  "action_items": [
    {{"item": "...", "owner": "...", "due": "..."}}
  ],
  "key_decisions": ["...", "..."],
  "speaker_mapping": {{"Speaker 0": "...", "Speaker 1": "..."}},
  "manual_notes": ["...", "..."]
}}"""

        result = self._chat(
            "You are a meeting assistant. Return structured JSON analysis only.",
            prompt
        )

        # Strip markdown code fences if present
        if result.startswith("```"):
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]

        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"raw_analysis": result}
