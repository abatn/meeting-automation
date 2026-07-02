"""
AlertManager → Supabase Adapter (direkt)

Umgeht OpenHive Webhook-Endpoint und postet direkt in die Supabase DB.
Einfacher und zuverlässiger als der indirekte Weg über OpenHive.

Flow: AlertManager → Adapter → Supabase REST API → messages-Tabelle
"""

import os
import json
import logging
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alert-adapter")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hwtxbuvokwgojgpvpjdx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_secret_N71vl2S3KD1ygkAikkv7NQ_v64h1NwN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "52700bb0-e563-4e11-b3be-e9d54b402fe3")


def format_alert(alert_group: dict) -> dict:
    alerts = alert_group.get("alerts", [])
    status = alert_group.get("status", "firing")
    lines = []
    for alert in alerts:
        severity = alert.get("labels", {}).get("severity", "unknown")
        summary = alert.get("annotations", {}).get("summary", "No summary")
        description = alert.get("annotations", {}).get("description", "")
        icon = "🔴" if severity == "critical" else "🟡"
        lines.append(f"{icon} **{summary}**\n{description}\nStatus: {status}")
    return {"content": "\n\n".join(lines) if lines else "Empty alert", "channel_id": CHANNEL_ID}


class AlertHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            alert_group = json.loads(body)
            if isinstance(alert_group, list):
                alert_group = {"alerts": alert_group, "status": "firing"}

            payload = format_alert(alert_group)
            data = json.dumps(payload).encode("utf-8")

            req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/messages",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Prefer": "return=minimal",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Alert posted to Supabase: {resp.status}")
                self.send_response(200)
                self.end_headers()

        except Exception as e:
            logger.error(f"Failed to forward alert: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"status": "healthy"}')

    def log_message(self, format, *args):
        logger.info(format % args)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    logger.info(f"Starting Alert Adapter on port {port}")
    server = HTTPServer(("0.0.0.0", port), AlertHandler)
    server.serve_forever()
