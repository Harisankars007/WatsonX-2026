"""
Phase 2: Capture meeting audio using PyAudio (BlackHole virtual device on macOS)
and stream it to IBM Speech to Text via WebSocket for live transcription.
"""

import pyaudio
import threading
import logging
import base64
import json
import time
import queue
import audioop
import websocket
from websocket import ABNF

from config import (
    STT_WS_URL, STT_API_KEY,
    AUDIO_SAMPLE_RATE, AUDIO_STT_RATE, AUDIO_CHANNELS, AUDIO_CHUNK_SIZE,
    VIRTUAL_AUDIO_DEVICE
)

log = logging.getLogger("MeetBot.Audio")


# Downsample ratio: BlackHole native 48000 → IBM STT 16000
_DOWNSAMPLE_RATIO = AUDIO_SAMPLE_RATE // AUDIO_STT_RATE   # = 3


def find_audio_device(name=VIRTUAL_AUDIO_DEVICE):
    """Find the index of a named audio input device."""
    p = pyaudio.PyAudio()
    device_index = None
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if name.lower() in info["name"].lower() and info["maxInputChannels"] > 0:
            device_index = i
            log.info(f"🎙️ Found audio device: {info['name']} (index {i})")
            break
    p.terminate()
    if device_index is None:
        log.warning(f"⚠️ Device '{name}' not found. Using default input device.")
    return device_index


class LiveTranscriber:
    """
    Streams audio from virtual device to IBM STT WebSocket.
    Calls on_transcript(text, is_final) whenever a transcription arrives.
    """

    def __init__(self, on_transcript):
        self.on_transcript    = on_transcript
        self.audio_queue      = queue.Queue()
        self.running          = False
        self.ws               = None
        self.ws_thread        = None
        self.audio_thread     = None
        self.device_index     = find_audio_device()

    # ── WebSocket callbacks ──────────────────────────────────────

    def _on_ws_open(self, ws):
        log.info("🔗 IBM STT WebSocket connected.")
        # Tell IBM STT we are sending 16kHz mono PCM
        start_msg = json.dumps({
            "action": "start",
            "content-type": f"audio/l16;rate={AUDIO_STT_RATE};channels=1",
            "interim_results": True,
            "speaker_labels": False,
            "timestamps": True,
            "max_alternatives": 1,
            "inactivity_timeout": -1
        })
        ws.send(start_msg)

        # Start sending audio chunks
        def send_audio():
            while self.running:
                try:
                    chunk = self.audio_queue.get(timeout=1)
                    # Send raw binary audio using ABNF.OPCODE_BINARY
                    ws.send(chunk, opcode=ABNF.OPCODE_BINARY)
                except queue.Empty:
                    continue
                except Exception as e:
                    log.warning(f"Audio send error: {e}")
                    break
            try:
                ws.send(json.dumps({"action": "stop"}))
            except Exception:
                pass

        threading.Thread(target=send_audio, daemon=True).start()

    def _on_ws_message(self, ws, message):
        data = json.loads(message)

        if "results" in data:
            for result in data["results"]:
                alternatives = result.get("alternatives", [])
                if alternatives:
                    text      = alternatives[0].get("transcript", "").strip()
                    is_final  = result.get("final", False)
                    if text:
                        self.on_transcript(text, is_final)

    def _on_ws_error(self, ws, error):
        log.error(f"❌ WebSocket error: {error}")

    def _on_ws_close(self, ws, code, msg):
        log.info(f"🔌 WebSocket closed: {code} {msg}")
        # Auto-reconnect if bot is still running
        if self.running:
            log.info("🔄 Reconnecting to IBM STT in 3 seconds...")
            time.sleep(3)
            # Drain stale audio that built up during the gap — sending it
            # would cause IBM STT to process old/silent frames first.
            drained = 0
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    drained += 1
                except queue.Empty:
                    break
            if drained:
                log.info(f"🧹 Drained {drained} stale audio chunks before reconnect.")
            threading.Thread(target=self._connect_ws, daemon=True).start()

    # ── Audio capture ────────────────────────────────────────────

    def _capture_audio(self):
        p = pyaudio.PyAudio()
        # Open at BlackHole's native rate (48kHz) and stereo (2ch)
        stream = p.open(
            format=pyaudio.paInt16,
            channels=2,                     # BlackHole 2ch is stereo
            rate=AUDIO_SAMPLE_RATE,         # 48000 Hz native
            input=True,
            input_device_index=self.device_index,
            frames_per_buffer=AUDIO_CHUNK_SIZE
        )
        log.info("🎧 Audio capture started (48kHz stereo → 16kHz mono for STT).")
        while self.running:
            try:
                data = stream.read(AUDIO_CHUNK_SIZE, exception_on_overflow=False)
                # Step 1: stereo → mono (average L+R channels)
                mono = audioop.tomono(data, 2, 0.5, 0.5)
                # Step 2: 48kHz → 16kHz (factor of 3)
                downsampled, _ = audioop.ratecv(mono, 2, 1,
                                                AUDIO_SAMPLE_RATE, AUDIO_STT_RATE,
                                                None)
                self.audio_queue.put(downsampled)
            except Exception as e:
                log.warning(f"Audio read error: {e}")
        stream.stop_stream()
        stream.close()
        p.terminate()
        log.info("🎧 Audio capture stopped.")

    def _connect_ws(self):
        """Connect (or reconnect) to IBM STT WebSocket."""
        credentials = f"apikey:{STT_API_KEY}"
        encoded     = base64.b64encode(credentials.encode()).decode()
        headers     = {"Authorization": f"Basic {encoded}"}

        self.ws = websocket.WebSocketApp(
            STT_WS_URL,
            header=headers,
            on_open=self._on_ws_open,
            on_message=self._on_ws_message,
            on_error=self._on_ws_error,
            on_close=self._on_ws_close,
        )
        # ping_interval=0 disables websocket-level pings entirely.
        # IBM STT does NOT respond to ws pings — leaving them enabled causes
        # "ping/pong timed out" disconnects every ~40 seconds.
        self.ws_thread = threading.Thread(
            target=lambda: self.ws.run_forever(ping_interval=0),
            daemon=True
        )
        self.ws_thread.start()

    # ── Start / Stop ─────────────────────────────────────────────

    def start(self):
        self.running = True

        # Connect WebSocket
        self._connect_ws()

        # Give WS time to connect
        time.sleep(2)

        # Start audio capture
        self.audio_thread = threading.Thread(target=self._capture_audio, daemon=True)
        self.audio_thread.start()

        log.info("✅ Live transcription started.")

    def stop(self):
        self.running = False
        if self.ws:
            self.ws.close()
        log.info("⛔ Live transcription stopped.")
