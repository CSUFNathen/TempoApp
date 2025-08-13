# Tempo — Minecraft Server Control (CustomTkinter)

A lightweight desktop app to start/stop a Java Minecraft server, view live console,
watch memory usage, and see connected players.

## Features
- Start / stop with RAM flags (Xms/Xmx) and `nogui` toggle
- Console with color highlights and command entry
- Stats: memory sparkline
- Players: online list; max-players editor
- EULA helper
- Auto-detects your server `.jar` if placed next to the app

## ⚠️ Important
If Tempo is closed while the server is still running, the Minecraft server (a Java process) will keep running in the background.

**To stop it safely:**
1) Open **Task Manager** (`Ctrl` + `Shift` + `Esc`).
2) On the **Processes** tab, search for **java**.
3) Select **Java(TM) Platform SE binary** or **OpenJDK Platform binary** right click it and click **End task**.

If you’re unsure which Java process is the server or you have multiple Java apps open simply **restart your computer**.


## Download
➡️ **[Get Tempo for Windows (latest release)](../../releases/latest)**

## Run from source
```bash
python app.py

## License
- Code: TPNCL v1.0 — free for personal/educational use. **No commercial use or resale.**
- Assets (icons/logo): Non-Commercial, no standalone redistribution.
- Future versions may use a different license; this release stays under TPNCL v1.0.

