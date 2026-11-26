# Onn box tools for the Claude desktop app

Lets Claude chat (typed, dictated or voice mode) control the TV box. The brief's rules are enforced in code: commands only reach the box, read-only commands can't chain or write, core packages and the streaming apps can't be disabled, nothing can be uninstalled, and every disable/enable is logged to `changes.md`.

Tools: `read_brief`, `box_status`, `read_box`, `disable_package`, `enable_package`, `press_key`, `open_app`.

## Setup

1. `py -3.12 -m pip install -r server\requirements.txt`
2. Install the Claude desktop app (claude.com/download) and sign in.
3. In the app: Settings → Developer → Edit Config. Add this, using your own Windows user name. If the file already has an `mcpServers` section, put `onn-box` inside it.

   ```json
   {
     "mcpServers": {
       "onn-box": {
         "command": "py",
         "args": ["-3.12", "C:\\Users\\<you>\\onn-tv-stick\\server\\onn_box.py"]
       }
     }
   }
   ```
4. Quit the app completely (system tray → Quit) and reopen it.
5. In a new chat, ask: "Is the TV box connected?" Claude should ask to use `box_status`.

If Claude can't find adb, add `"env": {"ADB_PATH": "<full path to adb.exe>"}` next to `args` (`where.exe adb` shows the path).
