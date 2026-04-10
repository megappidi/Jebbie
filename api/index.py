"""
Vercel serverless function — receives /jobs Slack slash command
Uses only stdlib (no external dependencies)
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request


GITHUB_PAT  = os.environ.get("GITHUB_PAT", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")


def trigger_github_workflow():
    url     = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/job-scan.yml/dispatches"
    payload = json.dumps({"ref": "main", "inputs": {"on_demand": "true"}}).encode()
    req     = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"token {GITHUB_PAT}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 204
    except urllib.error.HTTPError as e:
        print(f"GitHub API error: {e.code} {e.reason}")
        return False


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        success = trigger_github_workflow()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        if success:
            msg = {"text": "⚡ Scanning now... results dropping in your channel in ~90 seconds."}
        else:
            msg = {"text": "❌ Couldn't trigger scan — check GITHUB_PAT and GITHUB_REPO in Vercel env vars."}
        self.wfile.write(json.dumps(msg).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Jebbie is running.")

    def log_message(self, format, *args):
        pass
