#!/usr/bin/env python3
"""
ToolRadar Server
Serves the web UI from web/ and exposes:
  GET /api/tools    — returns data/tools.json
  GET /api/refresh  — triggers background rescrape
  GET /api/status   — returns scraper status
"""

import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

PORT      = 8742
BASE_DIR  = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "tools.json"
WEB_DIR   = BASE_DIR / "web"

_state = {"running": False, "last_error": None}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path
        if   path == "/api/tools":   self._tools()
        elif path == "/api/refresh": self._refresh()
        elif path == "/api/status":  self._status()
        else:                        super().do_GET()

    # ── API handlers ──────────────────────────────────────────────────────────

    def _tools(self):
        if DATA_FILE.exists():
            body = DATA_FILE.read_bytes()
        else:
            body = json.dumps({
                "last_updated": None, "total_tools": 0,
                "categories": [], "suggestion_of_the_day": None,
            }).encode()
        self._send_json(200, body)

    def _refresh(self):
        if _state["running"]:
            self._send_json(200, json.dumps({"status": "already_running"}).encode())
            return

        _state["running"]    = True
        _state["last_error"] = None

        def _run():
            try:
                r = subprocess.run(
                    [sys.executable, str(BASE_DIR / "scraper.py")],
                    capture_output=True, text=True, timeout=240,
                )
                if r.returncode != 0:
                    _state["last_error"] = r.stderr[:300]
            except Exception as e:
                _state["last_error"] = str(e)
            finally:
                _state["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        self._send_json(202, json.dumps({"status": "started"}).encode())

    def _status(self):
        self._send_json(200, json.dumps(_state).encode())

    def _send_json(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass  # silence per-request logs


# ── Helpers ───────────────────────────────────────────────────────────────────

def _needs_update() -> bool:
    if not DATA_FILE.exists():
        return True
    try:
        data = json.loads(DATA_FILE.read_text())
        last = data.get("last_updated")
        if not last:
            return True
        age = (datetime.now() - datetime.fromisoformat(last)).days
        return age >= 7
    except Exception:
        return True


def main():
    print("⚡ ToolRadar")
    print("━" * 40)

    if _needs_update():
        print("📡 Data missing or stale — running initial fetch (~60 s)...\n")
        from scraper import run_scraper
        run_scraper()
    else:
        data = json.loads(DATA_FILE.read_text())
        last = data.get("last_updated", "")[:10]
        print(f"✅ {data['total_tools']} tools loaded  (last updated: {last})")

    if not os.environ.get("TOOLRADAR_NO_BROWSER"):
        def _open():
            time.sleep(1.2)
            webbrowser.open(f"http://localhost:{PORT}")
        threading.Thread(target=_open, daemon=True).start()

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n🚀 Running at http://localhost:{PORT}")
        print("   Press Ctrl+C to stop\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Stopped")


if __name__ == "__main__":
    main()
