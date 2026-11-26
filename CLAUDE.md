# Onn Google TV Box – Claude Code Brief

Working notes for reprogramming the Onn box live over ADB.

## Setup

- Device: Walmart Onn 4K streaming box (older model, Google TV with Google Assistant, not Gemini), ~8GB storage, 2GB RAM.
- Connected to an RCA flat-screen TV by HDMI. HDMI-CEC is on, so the Onn remote controls TV power.
- A Telus cable box sits on a second HDMI input.
- Box IP on home Wi-Fi: `192.168.1.65` (port `5555`). Developer options and USB debugging are on.
- Controlling computer: Windows 10 laptop. adb comes from Google Platform Tools (installed with winget, on PATH). scrcpy was not found on this laptop; reinstall with `winget install -e --id Genymobile.scrcpy` if screen mirroring is needed.

## Connecting

```
adb connect 192.168.1.65:5555
adb devices
```

If the IP changes, check it on the box: Settings → Network & Internet → Wi-Fi network.

Run adb as plain `adb` (it is on PATH), never by full path.

## Goals

- Lean, fast and efficient: no ads, nothing unnecessary.
- Replace the stock Google TV home with a clean launcher (e.g. Projectivy Launcher).
- Privacy: turn off ad personalization, usage and diagnostics sharing, etc. Consider DNS-level blocking (e.g. NextDNS via Private DNS).
- Keep the streaming apps: Netflix, YouTube, Prime Video, Disney+.
- Later: a custom voice assistant app using a cloud model (Gemini Flash free tier), mapped to the remote's assistant button (e.g. Button Mapper). A laptop or phone could also do hands-free listening and send commands over ADB.

## Rules for Claude Code

- Explain each command in one line before running it. Ask before anything that removes or changes system behaviour.
- Prefer reversible changes. Disable bloat with `adb shell pm disable-user --user 0 <package>`; undo with `adb shell pm enable --user 0 <package>`. No full uninstalls of system packages.
- Never disable core packages: system UI, Google Play Services, Play Store, input/keyboard service, remote and Bluetooth services, or the current launcher before a new one is installed and set.
- Log every disabled package or changed setting, with its undo command, in `changes.md`.
- Check free space (`adb shell df /data`) before installing anything big.
- Before testing a new launcher, confirm the stock home can be restored.

## Handy commands

| Task | Command |
|---|---|
| List installed packages | `adb shell pm list packages` |
| List third-party apps | `adb shell pm list packages -3` |
| List disabled packages | `adb shell pm list packages -d` |
| Install an APK | `adb install app.apk` |
| Open an app | `adb shell monkey -p <package> 1` |
| Press a remote key | `adb shell input keyevent <code>` (3 home, 4 back, 26 power) |
| Open settings | `adb shell am start -a android.settings.SETTINGS` |
| Reboot | `adb reboot` |
