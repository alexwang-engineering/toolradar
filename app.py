#!/usr/bin/env python3
"""
ToolRadar Desktop App
Opens a native macOS window (pywebview / WebKit) around the local web UI.
External tool URLs open in a child in-app window — nothing leaves the app.
"""

import os
import sys
import socket
import threading
import time
from pathlib import Path

PORT     = 8742
BASE_DIR = Path(__file__).parent


# ── Wait for the HTTP server to accept connections ────────────────────────────

def _wait_ready(host="localhost", port=PORT, tries=50, delay=0.25) -> bool:
    for _ in range(tries):
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(delay)
    return False


# ── Server thread ─────────────────────────────────────────────────────────────

def _start_server():
    os.environ["TOOLRADAR_NO_BROWSER"] = "1"
    sys.path.insert(0, str(BASE_DIR))
    from server import main
    main()


# ── pywebview JS API ──────────────────────────────────────────────────────────

class Api:
    """Methods callable from JS as `pywebview.api.<name>(...)`.
    All methods run on the pywebview worker thread — don't block the UI.
    """

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _parse_gh(self, url):
        import re
        m = re.match(r'https?://github\.com/([^/?#]+)/([^/?#]+?)(?:\.git)?\/?$', url)
        return (m.group(1), m.group(2)) if m else (None, None)

    def _gh(self, args, timeout=8):
        import subprocess, shutil, os
        gh = shutil.which("gh")
        if not gh:
            for p in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
                if os.path.exists(p): gh = p; break
        if not gh:
            return -2, "", "gh CLI not found — run: brew install gh"
        try:
            r = subprocess.run([gh] + args, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return -2, "", "gh CLI not found"
        except subprocess.TimeoutExpired:
            return -1, "", "Timed out"
        except Exception as e:
            return -1, "", str(e)

    # ── Open URL ──────────────────────────────────────────────────────────────

    def open_tool_url(self, url: str, title: str = "") -> None:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return
        try:
            import webview
            # Must be called from a non-main thread (which Api methods are) so that
            # webview.create_window() triggers guilib.create_window() immediately.
            webview.create_window(title or url, url, width=1280, height=900)
        except Exception:
            import subprocess
            subprocess.Popen(["open", url])

    def is_app(self) -> bool:
        return True

    # ── Repo state (all checks in parallel) ───────────────────────────────────

    def check_repo_state(self, url: str) -> dict:
        import os, threading
        owner, repo = self._parse_gh(url)
        if not owner:
            return {"error": "Not a GitHub URL"}

        cloned_path = os.path.expanduser(f"~/tools/{repo}")
        results = {}

        def _star():
            code, _, _ = self._gh(["api", f"user/starred/{owner}/{repo}"], timeout=5)
            results["star"] = code

        def _watch():
            code, out, _ = self._gh(["api", f"repos/{owner}/{repo}/subscription"], timeout=5)
            results["watch_code"] = code
            results["watch_out"] = out

        t1, t2 = threading.Thread(target=_star), threading.Thread(target=_watch)
        t1.start(); t2.start()
        t1.join(6);  t2.join(6)

        star_code  = results.get("star", -1)
        watch_code = results.get("watch_code", -1)
        watch_out  = results.get("watch_out", "")

        return {
            "starred":      star_code == 0,
            "watching":     watch_code == 0 and '"subscribed": true' in watch_out,
            "cloned":       os.path.exists(cloned_path),
            "cloned_path":  cloned_path if os.path.exists(cloned_path) else None,
            "gh_available": star_code != -2,
        }

    # ── Star / unstar ─────────────────────────────────────────────────────────

    def star_repo(self, url: str) -> dict:
        owner, repo = self._parse_gh(url)
        if not owner: return {"success": False, "error": "Not a GitHub URL"}
        code, _, err = self._gh(["api", f"user/starred/{owner}/{repo}", "-X", "PUT"])
        return {"success": code == 0, "error": err or None}

    def unstar_repo(self, url: str) -> dict:
        owner, repo = self._parse_gh(url)
        if not owner: return {"success": False, "error": "Not a GitHub URL"}
        code, _, err = self._gh(["api", f"user/starred/{owner}/{repo}", "-X", "DELETE"])
        return {"success": code == 0, "error": err or None}

    # ── Watch / unwatch ───────────────────────────────────────────────────────

    def watch_repo(self, url: str) -> dict:
        owner, repo = self._parse_gh(url)
        if not owner: return {"success": False, "error": "Not a GitHub URL"}
        code, _, err = self._gh(["api", f"repos/{owner}/{repo}/subscription",
                                  "-X", "PUT", "-f", "subscribed=true"])
        return {"success": code == 0, "error": err or None}

    def unwatch_repo(self, url: str) -> dict:
        owner, repo = self._parse_gh(url)
        if not owner: return {"success": False, "error": "Not a GitHub URL"}
        code, _, err = self._gh(["api", f"repos/{owner}/{repo}/subscription", "-X", "DELETE"])
        return {"success": code == 0, "error": err or None}

    # ── Clone / update ────────────────────────────────────────────────────────

    def clone_repo(self, url: str) -> dict:
        import subprocess, os
        owner, repo = self._parse_gh(url)
        if not owner: return {"success": False, "error": "Not a GitHub repo URL"}
        dest = os.path.expanduser(f"~/tools/{repo}")
        if os.path.exists(dest):
            return {"success": True, "already": True, "path": dest}
        os.makedirs(os.path.expanduser("~/tools"), exist_ok=True)
        try:
            r = subprocess.run(["git", "clone", "--depth=1", url, dest],
                               capture_output=True, text=True, timeout=90)
            if r.returncode == 0:
                return {"success": True, "path": dest}
            return {"success": False, "error": (r.stderr or r.stdout).strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timed out after 90s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_repo(self, repo_name: str) -> dict:
        import subprocess, os
        dest = os.path.expanduser(f"~/tools/{repo_name}")
        if not os.path.exists(dest):
            return {"success": False, "error": "Not cloned yet"}
        try:
            r = subprocess.run(["git", "pull"], cwd=dest, capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                return {"success": True, "output": r.stdout.strip() or "Already up to date"}
            return {"success": False, "error": r.stderr.strip()}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timed out after 60s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── pip install ───────────────────────────────────────────────────────────

    def pip_install(self, package: str) -> dict:
        import subprocess
        try:
            r = subprocess.run(["pip3", "install", package],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0:
                return {"success": True}
            err = next((l for l in reversed(r.stderr.splitlines()) if l.strip()), r.stderr)
            return {"success": False, "error": err}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timed out after 120s"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── GitHub Desktop ────────────────────────────────────────────────────────

    def open_in_github_desktop(self, url: str) -> dict:
        import subprocess
        subprocess.Popen(["open", f"x-github-client://openRepo/{url}"])
        return {"success": True}

    def reveal_path(self, path: str) -> None:
        import subprocess
        subprocess.Popen(["open", "-R", path])

    # ── Live repo info ────────────────────────────────────────────────────────

    def get_repo_info(self, url: str) -> dict:
        import json
        owner, repo = self._parse_gh(url)
        if not owner:
            return {"error": "Not a GitHub URL"}
        code, out, _ = self._gh(["api", f"repos/{owner}/{repo}"], timeout=10)
        if code != 0:
            return {"error": "api_failed"}
        try:
            d = json.loads(out)
            lic = d.get("license") or {}
            return {
                "stars":       d.get("stargazers_count"),
                "forks":       d.get("forks_count"),
                "language":    d.get("language"),
                "license":     lic.get("spdx_id") if lic.get("spdx_id") != "NOASSERTION" else None,
                "topics":      d.get("topics") or [],
                "homepage":    d.get("homepage") or None,
                "open_issues": d.get("open_issues_count"),
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Clipboard ─────────────────────────────────────────────────────────────

    def copy_to_clipboard(self, text: str) -> dict:
        import subprocess
        try:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    try:
        import webview
    except ImportError:
        print("⚠  pywebview not found — falling back to browser mode")
        os.environ.pop("TOOLRADAR_NO_BROWSER", None)
        from server import main as server_main
        server_main()
        return

    # Start HTTP server in background thread
    threading.Thread(target=_start_server, daemon=True).start()

    print("⚡ ToolRadar — waiting for server...")
    if not _wait_ready():
        print("❌  Server did not start in time.")
        sys.exit(1)

    api = Api()
    webview.create_window(
        "⚡ ToolRadar",
        f"http://localhost:{PORT}",
        width=1440,
        height=920,
        min_size=(920, 640),
        js_api=api,
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
