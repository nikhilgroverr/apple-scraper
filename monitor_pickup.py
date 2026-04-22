#!/usr/bin/env python3
"""Monitor Apple India iPhone pickup availability and alert when it changes to 'Today'."""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


DEFAULT_URL = "https://www.apple.com/in/shop/buy-iphone/iphone-16/6.1%22-display-128gb-black"


@dataclass
class PickupSnapshot:
    text: str
    checked_at_utc: str


@dataclass
class MonitorConfig:
    url: str
    state_file: Path
    timeout_ms: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Apple pickup availability and alert when it changes to Today."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Product page URL to monitor")
    parser.add_argument(
        "--state-file",
        default="state/pickup_state.json",
        help="Where the previous pickup value is stored",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Page load and selector timeout in seconds",
    )
    return parser.parse_args()


def extract_pickup_text(url: str, timeout_ms: int) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(8000)
            # This locator catches text like: "Pick up Tomorrow at Apple Saket"
            locator = page.locator(r"text=/Pick\s*up\s+.*\s+at/i").first
            locator.wait_for(timeout=timeout_ms)
            text = locator.inner_text(timeout=timeout_ms).strip()
            return " ".join(text.split())
        except PlaywrightTimeoutError as exc:
            raise RuntimeError(
                "Could not find pickup availability text. Apple may have changed the page structure."
            ) from exc
        finally:
            browser.close()


def load_previous_snapshot(path: Path) -> Optional[PickupSnapshot]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return PickupSnapshot(text=data["text"], checked_at_utc=data["checked_at_utc"])


def save_snapshot(path: Path, text: str) -> PickupSnapshot:
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = PickupSnapshot(
        text=text,
        checked_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    path.write_text(json.dumps(snapshot.__dict__, indent=2), encoding="utf-8")
    return snapshot


def send_email_alert(subject: str, body: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_from = os.getenv("ALERT_FROM")
    email_to = os.getenv("ALERT_TO")

    required = {
        "SMTP_HOST": smtp_host,
        "SMTP_USER": smtp_user,
        "SMTP_PASS": smtp_pass,
        "ALERT_FROM": email_from,
        "ALERT_TO": email_to,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing email settings: " + ", ".join(missing) + ". "
            "Set env vars to receive notifications."
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def maybe_alert(prev: Optional[PickupSnapshot], current: PickupSnapshot, url: str) -> bool:
    prev_text = prev.text if prev else "<none>"
    changed_to_today = ("today" in current.text.lower()) and (
        prev is None or "today" not in prev.text.lower()
    )

    print(f"Previous: {prev_text}")
    print(f"Current : {current.text}")
    print(f"Checked : {current.checked_at_utc}")

    if not changed_to_today:
        print("No alert condition met.")
        return False

    subject = "Apple pickup changed to TODAY ✅"
    body = (
        "Pickup availability changed to TODAY.\n\n"
        f"Previous: {prev_text}\n"
        f"Current : {current.text}\n"
        f"Checked : {current.checked_at_utc}\n"
        f"URL     : {url}\n"
    )
    send_email_alert(subject, body)
    print("Alert sent.")
    return True


def main() -> int:
    args = parse_args()
    config = MonitorConfig(
        url=args.url,
        state_file=Path(args.state_file),
        timeout_ms=max(1, args.timeout_seconds) * 1000,
    )

    try:
        pickup_text = extract_pickup_text(config.url, config.timeout_ms)
    except Exception as exc:
        print(f"Error fetching pickup status: {exc}", file=sys.stderr)
        return 1

    previous = load_previous_snapshot(config.state_file)
    current = save_snapshot(config.state_file, pickup_text)

    try:
        maybe_alert(previous, current, config.url)
    except Exception as exc:
        print(f"Status changed but failed to send alert: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
