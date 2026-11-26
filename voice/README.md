# Voice mode

Talk to Claude Code hands-free on the Windows laptop. Say "Claude" and your request. For 20 seconds after each reply you can answer without the wake word. Say "goodbye" to stop.

## One-time setup

1. Install Python 3.12 from python.org. Tick "Add python.exe to PATH".
2. Install Claude Code for Windows (see code.claude.com/docs/en/setup). Open a terminal in this repo folder, run `claude` once and sign in with your Claude account.
3. In that terminal: `py -m pip install -r voice\requirements.txt`
4. If the box isn't authorized yet: `adb connect 192.168.1.65:5555` and accept the prompt on the TV.

## Run

Double-click `voice\Talk to Claude.bat`. The first run downloads the speech model (about 150 MB).

Options (add after `py talk.py` in a terminal):

- `--wake ""`: always listen, no wake word.
- `--window 30`: longer follow-up window.
- `--stt google`: faster on a slow laptop, but sends your audio to Google.
- `--model small.en`: more accurate, slower.

## Limits

- It hears the TV. Mute or turn it down while talking, or keep the wake word on.
- Each reply takes several seconds, because every turn starts Claude Code fresh.
- Voice replaces the permission prompt. `adb` commands are pre-approved; Claude is told to say what it will change and act only on your "yes". A misheard "yes" still counts, so listen to what it says first.
- Every turn counts against your Claude plan's usage.
