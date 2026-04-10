"""
Vercel serverless function — receives /jobs Slack slash command
Triggers GitHub Actions workflow and immediately acks Slack
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import requests


GITHUB_PAT  = os.environ["GITHUB_PAT"]   # Personal Access Token with repo + workflow scope
GITHUB_REPO = os.environ["GITHUB_REPO"]  # e.g. "meghana/job-bot"


def trigger_github_workflow():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/job-scan.yml/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "ref": "main",
        "inputs": {"on_demand": "true"},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    return r.status_code == 204  # GitHub returns 204 on success


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        success = trigger_github_workflow()

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        if success:
            msg = {"text": "⚡ Scanning now... dropping results in your channel in ~90 seconds."}
        else:
            msg = {"text": "❌ Couldn't trigger scan — check your GitHub token in Vercel env vars."}

        self.wfile.write(json.dumps(msg).encode())

    # Slack sometimes sends a GET to verify the endpoint
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Job Bot is running.")

    def log_message(self, format, *args):
        pass  # suppress default request logs
