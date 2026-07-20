"""Menu bar app: the localflow hub in the macOS status bar.

Run with `lf menubar`. It reflects both surfaces of localflow:

  * **Dictation** — read from the local state file that `localflow` (the
    push-to-talk app) writes, so the icon shows idle / recording /
    transcribing and the "Recent dictations" submenu re-copies past
    transcripts. Works whether or not the server is running.
  * **Meetings** — polled over HTTP from the server (`lf serve`); shows
    detection, live session, and start/stop control.

It also launches the dictation app and the server, so the whole thing can be
driven from the menu bar without a terminal.
"""

import os
import signal
import subprocess
import time
import webbrowser

import pyperclip
import requests
import rumps

from localflow import state
from localflow.config import load_config

_config = load_config()
BASE = f"http://127.0.0.1:{_config.server_port}"

IDLE_ICON = "🎙"
DETECTED_ICON = "🎙❗"
LIVE_ICON = "🔴"
REC_ICON = "🔴"
TRANS_ICON = "⏳"
DOWN_ICON = "🎙⚫"

RECENT_COUNT = 10


class LocalflowMenuBar(rumps.App):
    def __init__(self):
        super().__init__(IDLE_ICON, quit_button="Quit localflow menu bar")

        self.dictation_item = rumps.MenuItem("dictation: …")
        self.recent_menu = rumps.MenuItem("Recent dictations")
        self.dictate_launch_item = rumps.MenuItem(
            "Start dictation", callback=self.toggle_dictation
        )

        self.status_item = rumps.MenuItem("server: …")
        self.toggle_item = rumps.MenuItem(
            "Start meeting transcription", callback=self.toggle_meeting
        )
        self.dismiss_item = rumps.MenuItem("Dismiss detection", callback=self.dismiss)
        self.server_launch_item = rumps.MenuItem(
            "Start localflow server", callback=self.start_server
        )

        self.open_ui_item = rumps.MenuItem("Open web UI", callback=self.open_ui)
        self.open_notes_item = rumps.MenuItem(
            "Open notes folder", callback=self.open_notes
        )

        self.menu = [
            self.dictation_item,
            self.recent_menu,
            None,
            self.status_item,
            self.toggle_item,
            self.dismiss_item,
            None,
            self.dictate_launch_item,
            self.server_launch_item,
            None,
            self.open_ui_item,
            self.open_notes_item,
        ]

        self._session_active = False
        self._dictation_running = False
        self._server_up = False
        self._was_detected = False
        self._history_sig = None
        self._dictation_proc = None  # process we launched, if any

        self.timer = rumps.Timer(self.refresh, 2)
        self.timer.start()

    # ------------------------------------------------------------- polling ---

    def _fetch_meeting_status(self):
        try:
            return True, requests.get(BASE + "/meeting/status", timeout=3).json()
        except Exception:
            return False, {}

    def refresh(self, _timer=None) -> None:
        server_up, st = self._fetch_meeting_status()
        self._server_up = server_up

        dnow = state.read_status()
        self._dictation_running = bool(dnow.get("running"))
        dstatus = dnow.get("status", "idle")

        session = st.get("session")
        self._session_active = bool(session)
        detected = bool(st.get("detected"))

        # --- icon (single source of truth, by priority) ---
        self.title = self._pick_icon(
            session, detected, dstatus, self._dictation_running, server_up
        )

        # --- dictation line ---
        if dstatus == "recording":
            self.dictation_item.title = "dictation: ● recording"
        elif dstatus == "transcribing":
            self.dictation_item.title = "dictation: transcribing…"
        elif self._dictation_running:
            self.dictation_item.title = "dictation: idle (hold hotkey to talk)"
        else:
            self.dictation_item.title = "dictation: not running"
        self.dictate_launch_item.title = (
            "Stop dictation" if self._dictation_running else "Start dictation"
        )

        # --- meeting / server line ---
        if session:
            minutes, seconds = divmod(session["seconds"], 60)
            self.status_item.title = (
                f"recording: {session['title']} — "
                f"{minutes}m{seconds:02d}s, {session['segment_count']} segments"
            )
            self.toggle_item.title = "Stop & save notes"
        else:
            self.toggle_item.title = "Start meeting transcription"
            if not server_up:
                self.status_item.title = "server: down (start it below)"
            elif detected:
                platform = st.get("platform") or "?"
                self.status_item.title = f"meeting detected ({platform})"
                if not self._was_detected:
                    rumps.notification(
                        "localflow", "Meeting detected",
                        f"{platform} — start transcription from the menu bar.",
                    )
            else:
                busy = "mic in use" if st.get("mic_busy") else "idle"
                self.status_item.title = f"server up · watching · {busy}"
        self._was_detected = detected

        # --- server launcher ---
        if server_up:
            self.server_launch_item.title = "localflow server: running ✓"
            self.server_launch_item.set_callback(None)
        else:
            self.server_launch_item.title = "Start localflow server"
            self.server_launch_item.set_callback(self.start_server)

        self._rebuild_recent()

    def _pick_icon(self, session, detected, dstatus, drunning, server_up) -> str:
        if session:
            return LIVE_ICON
        if dstatus == "recording":
            return REC_ICON
        if dstatus == "transcribing":
            return TRANS_ICON
        if detected:
            return DETECTED_ICON
        if not server_up and not drunning:
            return DOWN_ICON
        return IDLE_ICON

    def _rebuild_recent(self) -> None:
        history = state.read_history(RECENT_COUNT)
        sig = (len(history), history[0]["ts"] if history else 0)
        if sig == self._history_sig:
            return
        self._history_sig = sig

        self.recent_menu.clear()
        if not history:
            self.recent_menu.add(rumps.MenuItem("(none yet)"))
            return
        for entry in history:
            self.recent_menu.add(
                rumps.MenuItem(
                    self._recent_label(entry),
                    callback=self._copy_callback(entry["text"]),
                )
            )

    @staticmethod
    def _recent_label(entry: dict) -> str:
        stamp = time.strftime("%H:%M", time.localtime(entry.get("ts", 0)))
        snippet = " ".join((entry.get("text") or "").split())
        if len(snippet) > 44:
            snippet = snippet[:43] + "…"
        return f"{stamp}  {snippet}"

    def _copy_callback(self, text: str):
        def cb(_item) -> None:
            try:
                pyperclip.copy(text)
                rumps.notification("localflow", "Copied to clipboard", text[:80])
            except Exception as exc:
                rumps.notification("localflow", "Copy failed", str(exc)[:100])
        return cb

    # ------------------------------------------------------------- actions ---

    def toggle_dictation(self, _item) -> None:
        if self._dictation_running:
            self._stop_dictation()
        else:
            try:
                self._dictation_proc = subprocess.Popen(["localflow"])
            except Exception as exc:
                rumps.notification("localflow", "Could not start dictation", str(exc)[:100])
        self.refresh()

    def _stop_dictation(self) -> None:
        if self._dictation_proc and self._dictation_proc.poll() is None:
            self._dictation_proc.terminate()
            self._dictation_proc = None
            return
        # Externally-launched dictation: signal it by the pid it recorded.
        pid = state.read_status().get("pid")
        if pid:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except Exception:
                pass

    def start_server(self, _item) -> None:
        try:
            subprocess.Popen(["localflow-server"])
            rumps.notification("localflow", "Starting server", "give it a few seconds…")
        except Exception as exc:
            rumps.notification("localflow", "Could not start server", str(exc)[:100])

    def toggle_meeting(self, _item) -> None:
        try:
            if self._session_active:
                self.title = IDLE_ICON
                self.status_item.title = "summarizing & saving…"
                resp = requests.post(BASE + "/meeting/stop", timeout=600)
                resp.raise_for_status()
                saved = resp.json()
                rumps.notification("localflow", "Notes saved", saved["notes_path"])
            else:
                resp = requests.post(
                    BASE + "/meeting/start",
                    json={"title": "Meeting", "category": ""},
                    timeout=10,
                )
                resp.raise_for_status()
        except Exception as exc:
            rumps.notification("localflow", "Error", str(exc)[:120])
        self.refresh()

    def dismiss(self, _item) -> None:
        try:
            requests.post(BASE + "/meeting/dismiss", timeout=3)
        except Exception:
            pass
        self.refresh()

    def open_ui(self, _item) -> None:
        webbrowser.open(BASE)

    def open_notes(self, _item) -> None:
        from pathlib import Path

        folder = Path(_config.vault_path).expanduser() / _config.notes_folder
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(folder)], check=False)


def main() -> None:
    LocalflowMenuBar().run()


if __name__ == "__main__":
    main()
