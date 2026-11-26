"""Hands-free voice conversation with Claude Code, for Windows.

Say "Claude" followed by your request. For a short window after each reply you
can answer without the wake word, so a back-and-forth flows naturally.
Say "goodbye" to stop. Replies are spoken with the built-in Windows voice.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import speech_recognition as sr

try:
    import winsound
except ImportError:  # not on Windows
    winsound = None

REPO = Path(__file__).resolve().parent.parent
ALLOWED_TOOLS = "Bash(adb *),Bash(adb.exe *),Read,Edit,Write"
# Speech-to-text often mishears "Claude", so accept the usual variants.
WAKE_ALIASES = {"claude": ["claude", "claud", "cloud", "clyde", "clod", "clawed"]}
EXIT_PHRASES = {"goodbye", "good bye", "stop listening"}
# Phrases Whisper tends to invent from background noise.
NOISE_PHRASES = {"you", "thanks for watching", "thank you for watching"}

VOICE_PROMPT = (
    "The user is talking to you by voice and your reply is read aloud by text-to-speech. "
    "Answer in one to three short, plain sentences. No markdown, lists, code blocks or symbols. "
    "Describe commands and package names in words instead of reading them out, unless asked. "
    "Before running any command that changes the TV box or its settings, say what you will do "
    "and ask; run it only after the user says yes in their next message. "
    "Speech-to-text can mishear, so if a request is unclear or sounds risky, ask first. "
    "adb is on PATH: run it with the Bash tool as plain adb, never by full path, "
    "never through PowerShell, and one adb command per call. "
    "The user cannot approve permission prompts in this mode, so never ask them to; "
    "if a command is blocked, say which one."
)

SPEAK_PS = (
    "Add-Type -AssemblyName System.Speech; "
    "$v = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$v.Speak([Console]::In.ReadToEnd())"
)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wake", default="claude", help='wake word; "" to always listen')
    p.add_argument("--window", type=float, default=20,
                   help="seconds after a reply when no wake word is needed")
    p.add_argument("--stt", choices=["whisper", "google"], default="whisper",
                   help="whisper runs locally; google is faster but sends audio to Google")
    p.add_argument("--model", default="base.en", help="Whisper model: tiny.en, base.en, small.en")
    p.add_argument("--pause", type=float, default=1.0, help="seconds of silence that end a phrase")
    p.add_argument("--max-phrase", type=float, default=30, help="longest phrase in seconds")
    return p.parse_args()


class Transcriber:
    def __init__(self, engine, model_size):
        self.engine = engine
        if engine == "whisper":
            from faster_whisper import WhisperModel
            print(f"Loading speech model {model_size} (the first run downloads it)...")
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def __call__(self, recognizer, audio):
        if self.engine == "google":
            try:
                return recognizer.recognize_google(audio)
            except sr.UnknownValueError:
                return ""
            except sr.RequestError as e:
                print(f"(Google speech service failed: {e})")
                return ""
        raw = audio.get_raw_data(convert_rate=16000, convert_width=2)
        pcm = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        segments, _ = self.model.transcribe(pcm, language="en", vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()


def wake_pattern(wake):
    if not wake:
        return None
    names = "|".join(map(re.escape, WAKE_ALIASES.get(wake, [wake])))
    return re.compile(rf"^\W*(?:(?:hey|ok|okay)\W+)?(?:{names})\b\W*", re.I)


def strip_wake(text, pattern):
    """Return the text after the wake word, or None if it doesn't start with one."""
    m = pattern.match(text) if pattern else None
    return text[m.end():] if m else None


def normalized(text):
    return re.sub(r"[^\w ]", "", text.lower()).strip()


def for_speech(text):
    text = re.sub(r"```.*?```", " I've put the details on screen. ", text, flags=re.S)
    text = re.sub(r"https?://\S+", "a link", text)
    text = re.sub(r"[`*_#>|]", "", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip()


def speak(text):
    print(f"Claude: {text}\n")
    spoken = for_speech(text)
    if spoken:
        subprocess.run(["powershell", "-NoProfile", "-Command", SPEAK_PS],
                       input=spoken, text=True)


def beep():
    if winsound:
        winsound.Beep(880, 120)


def ask_claude(claude, text, session_id, env):
    cmd = [claude, "-p", "--output-format", "json",
           "--allowedTools", ALLOWED_TOOLS,
           "--append-system-prompt", VOICE_PROMPT]
    if session_id:
        cmd += ["--resume", session_id]
    try:
        r = subprocess.run(cmd, input=text, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", cwd=REPO, env=env, timeout=600)
    except subprocess.TimeoutExpired:
        return "That took too long, so I stopped waiting.", session_id
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        err = (r.stderr or r.stdout).strip()
        return (err[-500:] if err else "Claude Code returned nothing."), session_id
    for d in data.get("permission_denials") or []:
        print(f"(blocked: {d.get('tool_name')} {json.dumps(d.get('tool_input'))})")
    return str(data.get("result", "")).strip(), data.get("session_id") or session_id


def main():
    args = parse_args()
    claude = shutil.which("claude")
    if not claude:
        sys.exit("Claude Code isn't on PATH. Install it and sign in first (see voice/README.md).")
    env = dict(os.environ)
    wake = args.wake.strip().lower()
    pattern = wake_pattern(wake)
    transcribe = Transcriber(args.stt, args.model)

    rec = sr.Recognizer()
    rec.pause_threshold = args.pause
    with sr.Microphone() as mic:
        print("Measuring background noise, stay quiet for a moment...")
        rec.adjust_for_ambient_noise(mic, duration=1.5)

    session_id = None
    window_until = 0.0
    speak(f"Ready. Say {wake} to start." if wake else "Ready. Go ahead.")
    while True:
        # Reopen the mic each turn so it never hears its own replies.
        with sr.Microphone() as mic:
            audio = rec.listen(mic, phrase_time_limit=args.max_phrase)
        started = time.monotonic() - len(audio.frame_data) / (audio.sample_rate * audio.sample_width)
        heard = transcribe(rec, audio)
        if not heard:
            continue

        request = strip_wake(heard, pattern)
        if request is None:
            if pattern and started > window_until:
                print(f'(ignored, say "{wake}" first: {heard})')
                continue
            if normalized(heard) in NOISE_PHRASES:
                continue
            request = heard
        print(f"You: {heard}")

        if normalized(request) in EXIT_PHRASES:
            speak("Bye.")
            return
        if not request.strip():  # just the wake word: prompt for the actual request
            speak("Yes?")
            window_until = time.monotonic() + args.window
            continue
        beep()

        print("Thinking...")
        reply, session_id = ask_claude(claude, request, session_id, env)
        speak(reply or "I didn't get a reply from Claude Code.")
        window_until = time.monotonic() + args.window


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
