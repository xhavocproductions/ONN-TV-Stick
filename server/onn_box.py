"""MCP server: lets the Claude desktop app (chat and voice mode) control the Onn TV box over adb.

The brief's safety rules are enforced here in code, not just requested: every command
targets the box only, read-only commands can't chain or redirect, core packages and the
streaming apps can't be disabled, nothing can be uninstalled, and every disable/enable is
logged to changes.md with its undo command.
"""

import datetime
import os
import re
import shutil
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

BOX = "192.168.1.65:5555"
REPO = Path(__file__).resolve().parent.parent
BRIEF = REPO / "CLAUDE.md"
LOG = REPO / "changes.md"
ADB = os.environ.get("ADB_PATH") or shutil.which("adb") or "adb"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

READ_PREFIXES = ("pm list", "pm path", "dumpsys", "getprop", "df", "settings get",
                 "cmd package list", "ps", "top -b -n 1", "cat /proc/meminfo", "wm size")
SAFE_ARGS = re.compile(r"^[\w .,:=/@+\-]+$")  # no ; | & < > ` $ or quotes: nothing chains or writes
PACKAGE = re.compile(r"^[A-Za-z]\w*(\.\w+)+$")
# Core parts the brief says never to disable. Substring match, so it errs on the safe side.
PROTECTED = ("systemui", "launcher", "setupwraith", ".gms", ".gsf", "vending", "inputmethod",
             "leanback.ime", "keyboard", "bluetooth", "btservices", "remote", "settings",
             "providers", "permission", "packageinstaller", "networkstack", "wifi", "webview",
             ".shell", "tvsetup")
KEEP = ("netflix", "youtube", "amazonvideo", "disney")
KEYS = {"home": 3, "back": 4, "up": 19, "down": 20, "left": 21, "right": 22, "select": 23,
        "volume_up": 24, "volume_down": 25, "power": 26, "menu": 82, "play_pause": 85,
        "mute": 164, "settings": 176}

mcp = FastMCP("onn-box", instructions=(
    "Controls the user's Onn Google TV box over adb. In a new conversation, call read_brief first. "
    "Before disable_package, say in plain words what the package does and wait for the user's yes. "
    "In voice conversations keep replies short and describe packages instead of spelling out names."
))


def adb(*args, timeout=60):
    run = dict(stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
               errors="replace", creationflags=NO_WINDOW)
    subprocess.run([ADB, "connect", BOX], timeout=15, **run)
    r = subprocess.run([ADB, "-s", BOX, *args], timeout=timeout, **run)
    out = (r.stdout + r.stderr).strip()
    return out[-20000:] or "(no output)"


def check_package(package, for_disable):
    if not PACKAGE.match(package):
        return "Refused: that isn't a valid package name."
    low = package.lower()
    if for_disable and (low == "android" or any(p in low for p in PROTECTED)):
        return f"Refused: {package} is a core package the brief says never to disable."
    if for_disable and any(k in low for k in KEEP):
        return f"Refused: {package} is one of the streaming apps the user wants to keep."
    return None


def log_change(change, command, undo):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"| {datetime.date.today()} | {change} | `{command}` | `{undo}` |\n")


@mcp.tool()
def read_brief() -> str:
    """Read the project brief: the TV box setup, the user's goals and the safety rules. Call first."""
    return BRIEF.read_text(encoding="utf-8")


@mcp.tool()
def box_status() -> str:
    """Check the TV box is connected and show its free storage. Read-only."""
    return f"State: {adb('get-state')}\n{adb('shell', 'df -h /data')}"


@mcp.tool()
def read_box(command: str) -> str:
    """Run a read-only shell command on the TV box. Allowed starts: 'pm list', 'pm path',
    'dumpsys', 'getprop', 'df', 'settings get', 'cmd package list', 'ps', 'top -b -n 1',
    'cat /proc/meminfo', 'wm size'. Examples: 'pm list packages -3', 'pm list packages -d',
    'dumpsys meminfo', 'getprop ro.build.version.release'. No pipes, quotes or redirects;
    filter the output yourself."""
    cmd = command.strip()
    if not cmd.startswith(READ_PREFIXES) or not SAFE_ARGS.match(cmd):
        return "Refused: only simple read-only commands. Allowed starts: " + ", ".join(READ_PREFIXES)
    return adb("shell", cmd)


@mcp.tool()
def disable_package(package: str) -> str:
    """Disable an app or system package on the TV box. Reversible with enable_package.
    Only call after telling the user what it is and getting their yes. Core packages and the
    user's streaming apps are refused. Each change is logged to changes.md."""
    if err := check_package(package, for_disable=True):
        return err
    cmd = f"pm disable-user --user 0 {package}"
    out = adb("shell", cmd)
    if "disabled" in out:
        log_change(f"Disabled {package}", f"adb shell {cmd}",
                   f"adb shell pm enable --user 0 {package}")
    return out


@mcp.tool()
def enable_package(package: str) -> str:
    """Re-enable a package on the TV box (undoes disable_package). Logged to changes.md."""
    if err := check_package(package, for_disable=False):
        return err
    cmd = f"pm enable --user 0 {package}"
    out = adb("shell", cmd)
    if "enabled" in out:
        log_change(f"Re-enabled {package}", f"adb shell {cmd}",
                   f"adb shell pm disable-user --user 0 {package}")
    return out


@mcp.tool()
def press_key(key: str) -> str:
    """Press a remote button on the TV box: home, back, up, down, left, right, select,
    play_pause, volume_up, volume_down, mute, menu, settings, power."""
    code = KEYS.get(key.strip().lower().replace(" ", "_"))
    if code is None:
        return "Unknown key. Use one of: " + ", ".join(KEYS)
    return adb("shell", f"input keyevent {code}")


@mcp.tool()
def open_app(package: str) -> str:
    """Open an app on the TV box by package name, e.g. com.netflix.ninja."""
    if err := check_package(package, for_disable=False):
        return err
    return adb("shell", f"monkey -p {package} -c android.intent.category.LEANBACK_LAUNCHER 1")


if __name__ == "__main__":
    # Start the adb daemon up front with no pipes attached, so it can't hold ours open.
    subprocess.run([ADB, "start-server"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    mcp.run()
