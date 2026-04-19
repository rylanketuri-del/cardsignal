from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import requests


@dataclass
class DeliverySettings:
    alert_webhook_url: str = ""
    alert_webhook_bearer_token: str = ""
    app_base_url: str = ""
    alert_sender_name: str = "CardChase AI"
    alert_from_email: str = "alerts@example.com"
    resend_api_key: str = ""


def build_notification_email(event_type: str, title: str, body_text: str, player_name: str | None = None, app_base_url: str = "") -> tuple[str, str]:
    label_map = {
        "hotness_jump": "Hotness jump",
        "buy_low": "Buy low",
        "most_chased": "Most chased",
        "daily_digest": "Daily digest",
    }
    event_label = label_map.get(event_type, "CardChase alert")
    cta = "Open CardChase"
    cta_url = app_base_url.rstrip('/') if app_base_url else ""
    hero_name = player_name or "MLB market update"
    safe_title = escape(title)
    safe_body = escape(body_text).replace("\n", "<br />")
    safe_event = escape(event_label)
    safe_name = escape(hero_name)
    safe_cta_url = escape(cta_url)
    html = f"""
    <html>
      <body style="margin:0;padding:0;background:#0a0d0f;font-family:Inter,Arial,sans-serif;color:#eef3f4;">
        <div style="max-width:640px;margin:0 auto;padding:24px;">
          <div style="background:linear-gradient(180deg,#111619 0%,#0d1215 100%);border:1px solid #243038;border-radius:24px;overflow:hidden;">
            <div style="padding:24px 24px 12px 24px;border-bottom:1px solid #243038;">
              <div style="color:#8bf08b;font-size:12px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;">CardChase AI • MLB</div>
              <h1 style="margin:12px 0 8px 0;font-size:28px;line-height:1.1;">{safe_title}</h1>
              <div style="display:inline-block;margin-top:4px;padding:8px 12px;border-radius:999px;background:rgba(139,240,139,.12);color:#8bf08b;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;">{safe_event}</div>
            </div>
            <div style="padding:24px;">
              <div style="background:#161d21;border:1px solid #243038;border-radius:18px;padding:18px 18px 16px 18px;margin-bottom:18px;">
                <div style="color:#9fb0b7;font-size:12px;letter-spacing:.12em;text-transform:uppercase;">Focus player</div>
                <div style="margin-top:8px;font-size:24px;font-weight:800;color:#eef3f4;">{safe_name}</div>
              </div>
              <p style="margin:0 0 18px 0;color:#d7e3e6;font-size:15px;line-height:1.65;">{safe_body}</p>
              <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
                <a href="{safe_cta_url or '#'}" style="display:inline-block;background:#3ecf6b;color:#07110a;text-decoration:none;font-weight:800;padding:12px 16px;border-radius:14px;">{cta}</a>
                <span style="color:#9fb0b7;font-size:13px;">Track hot MLB players, watchlist moves, and market momentum.</span>
              </div>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    text = f"{title}\n\n{event_label}: {hero_name}\n\n{body_text}\n\n{cta}: {cta_url or 'Open your CardChase dashboard'}"
    return html, text


class AlertDeliveryClient:
    def __init__(self, settings: DeliverySettings, timeout: int = 30):
        self.settings = settings
        self.timeout = timeout

    def send_webhook(self, payload: dict[str, Any]) -> tuple[bool, str]:
        if not self.settings.alert_webhook_url:
            return False, "webhook_not_configured"
        headers = {"Content-Type": "application/json"}
        if self.settings.alert_webhook_bearer_token:
            headers["Authorization"] = f"Bearer {self.settings.alert_webhook_bearer_token}"
        response = requests.post(
            self.settings.alert_webhook_url,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            return False, f"webhook_error:{response.status_code}"
        return True, "webhook_sent"

    def send_resend_email(self, to_email: str, subject: str, body_text: str, html_body: str | None = None) -> tuple[bool, str]:
        if not self.settings.resend_api_key:
            return False, "resend_not_configured"
        json_payload = {
            "from": f"{self.settings.alert_sender_name} <{self.settings.alert_from_email}>",
            "to": [to_email],
            "subject": subject,
            "text": body_text,
        }
        if html_body:
            json_payload["html"] = html_body
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {self.settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json=json_payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            return False, f"resend_error:{response.status_code}"
        return True, "email_sent"
