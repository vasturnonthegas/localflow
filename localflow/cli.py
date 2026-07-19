"""`lf` — command-line control for localflow.

Talks to the running localflow server over HTTP; `lf serve` / `lf dictate`
run the components themselves.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from localflow.config import load_config

console = Console()
_config = load_config()
BASE = f"http://127.0.0.1:{_config.server_port}"


def _get(path: str) -> dict:
    try:
        resp = requests.get(BASE + path, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        console.print(f"[red]server not running[/red] — start it with: [bold]lf serve[/bold]")
        sys.exit(1)


def _post(path: str, json: dict | None = None) -> dict:
    try:
        resp = requests.post(BASE + path, json=json, timeout=600)
    except requests.ConnectionError:
        console.print(f"[red]server not running[/red] — start it with: [bold]lf serve[/bold]")
        sys.exit(1)
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.reason)
        except Exception:
            detail = resp.reason
        console.print(f"[red]error:[/red] {detail}")
        sys.exit(1)
    return resp.json()


@click.group()
def cli() -> None:
    """localflow: local dictation + meeting transcription to Obsidian."""


@cli.command()
def status() -> None:
    """Server, watcher, and session state."""
    st = _get("/meeting/status")
    table = Table(show_header=False, box=None)
    table.add_row("server", "[green]up[/green]")
    watcher = "[green]watching[/green]" if st["watching"] else f"[red]off[/red] {st['watch_error']}"
    table.add_row("watcher", watcher)
    table.add_row("mic busy", "[yellow]yes[/yellow]" if st["mic_busy"] else "no")
    if st["detected"]:
        table.add_row("detected", f"[bold yellow]meeting ({st['platform'] or '?'})[/bold yellow]")
    session = st.get("session")
    if session:
        table.add_row(
            "session",
            f"[bold red]● {session['title']}[/bold red] ({session['category']}) "
            f"{session['seconds'] // 60}m{session['seconds'] % 60:02d}s, "
            f"{session['segment_count']} segments",
        )
    else:
        table.add_row("session", "none")
    if st.get("last_saved"):
        table.add_row("last saved", st["last_saved"]["notes_path"])
    console.print(table)


@cli.group()
def meeting() -> None:
    """Control meeting transcription sessions."""


@meeting.command("start")
@click.option("--title", "-t", default="Meeting", help="Note title.")
@click.option("--category", "-c", default="", help="Zoom/Teams/... (default: auto-detected).")
def meeting_start(title: str, category: str) -> None:
    """Start transcribing a meeting."""
    out = _post("/meeting/start", {"title": title, "category": category})
    console.print(f"[green]●[/green] transcribing — category [bold]{out['category']}[/bold]. "
                  f"Stop with: [bold]lf meeting stop[/bold]")


@meeting.command("stop")
def meeting_stop() -> None:
    """Stop, summarize, and write notes to the vault."""
    with console.status("summarizing and writing notes…"):
        out = _post("/meeting/stop")
    console.print(f"[green]saved[/green] ({out['segments']} segments)")
    console.print(f"  notes: {out['notes_path']}")
    console.print(f"  log:   {out['log_path']}")


@meeting.command("dismiss")
def meeting_dismiss() -> None:
    """Dismiss the current meeting-detected banner."""
    _post("/meeting/dismiss")
    console.print("dismissed")


def _render(st: dict) -> Panel:
    body = Text()
    if st["detected"] and not st.get("session"):
        body.append(f"⚑ meeting detected ({st['platform'] or '?'}) — lf meeting start\n\n",
                    style="bold yellow")
    session = st.get("session")
    if session:
        body.append(f"● {session['title']}", style="bold red")
        body.append(f"  {session['seconds'] // 60}m{session['seconds'] % 60:02d}s · "
                    f"{session['segment_count']} segments\n\n", style="dim")
        for seg in session["segments"]:
            body.append(f"[{seg['stamp']}] ", style="cyan")
            body.append(seg["text"] + "\n")
        if not session["segments"]:
            body.append("(listening — first segment lands after ~30s)\n", style="dim")
    else:
        mic = "mic in use" if st["mic_busy"] else "idle"
        body.append(f"no session · {mic}\n", style="dim")
        if st.get("last_saved"):
            body.append(f"last saved: {st['last_saved']['notes_path']}\n", style="green")
    state = "watching" if st["watching"] else "watcher off"
    return Panel(body, title=f"localflow — {state}", border_style="grey50")


@cli.command()
def watch() -> None:
    """Live dashboard: detection state and rolling transcript. Ctrl+C exits."""
    with Live(_render(_get("/meeting/status")), refresh_per_second=1, console=console) as live:
        while True:
            time.sleep(3)
            try:
                live.update(_render(_get("/meeting/status")))
            except SystemExit:
                raise
            except Exception:
                pass


@cli.command()
@click.option("--limit", "-n", default=10, help="How many recent notes to list.")
def notes(limit: int) -> None:
    """List recent meeting notes in the vault."""
    root = Path(_config.vault_path).expanduser() / _config.notes_folder
    if not root.exists():
        console.print(f"[dim]no notes yet ({root})[/dim]")
        return
    files = sorted(root.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    if not files:
        console.print(f"[dim]no notes yet ({root})[/dim]")
        return
    table = Table(box=None, header_style="dim")
    table.add_column("modified")
    table.add_column("category")
    table.add_column("note")
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%m-%d %H:%M")
        table.add_row(mtime, f.parent.name, str(f))
    console.print(table)


@cli.command()
@click.argument("query", nargs=-1, required=True)
def open(query: tuple[str, ...]) -> None:
    """Open the newest note matching QUERY words in Obsidian/default app."""
    root = Path(_config.vault_path).expanduser() / _config.notes_folder
    words = [w.lower() for w in query]
    matches = [
        f for f in root.rglob("*.md")
        if all(w in f.name.lower() for w in words)
    ]
    if not matches:
        console.print("[red]no match[/red]")
        sys.exit(1)
    newest = max(matches, key=lambda p: p.stat().st_mtime)
    subprocess.run(["open", str(newest)], check=False)
    console.print(f"opened {newest.name}")


@cli.command()
def serve() -> None:
    """Run the localflow server (UI at /, meeting API, transcription)."""
    from localflow.server import main as server_main
    server_main()


@cli.command()
def dictate() -> None:
    """Run push-to-talk dictation (same as the `localflow` command)."""
    from localflow.app import main as app_main
    app_main()


@cli.command()
def ui() -> None:
    """Open the web UI in the default browser."""
    subprocess.run(["open", BASE], check=False)


@cli.command()
def menubar() -> None:
    """Run the macOS menu bar app (mic icon, meeting control)."""
    from localflow.menubar import main as menubar_main
    menubar_main()


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
