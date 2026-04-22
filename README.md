# Apple India iPhone Pickup Monitor (Python)

This project checks the Apple India iPhone 16 buy page and notifies you when pickup changes to **Today** (for example, when it changes from *Tomorrow* to *Today*).

## What it monitors
- Product URL (default):
  `https://www.apple.com/in/shop/buy-iphone/iphone-16/6.1%22-display-128gb-black`
- Pickup text like:
  - `Pick up Tomorrow at Apple Saket`
  - `Pick up Today at Apple Saket`

## How it works
1. Opens the Apple product page using Playwright (headless Chromium).
2. Extracts the pickup banner text.
3. Stores the latest text in `state/pickup_state.json`.
4. Sends an email alert **only when the status changes to Today**.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Email alert configuration
Set these environment variables before running:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASS="your-app-password"
export ALERT_FROM="your-email@gmail.com"
export ALERT_TO="your-email@gmail.com"
```

> For Gmail, use an App Password (not your normal password).

## Run once
```bash
python monitor_pickup.py
```

Optional flags:
```bash
python monitor_pickup.py \
  --url "https://www.apple.com/in/shop/buy-iphone/iphone-16/6.1%22-display-128gb-black" \
  --state-file "state/pickup_state.json" \
  --timeout-seconds 60
```

## Run every 10 minutes (Linux/macOS cron)
Edit crontab:
```bash
crontab -e
```

Add:
```cron
*/10 * * * * cd /workspace/apple-scraper && /usr/bin/python3 monitor_pickup.py >> monitor.log 2>&1
```

## Notes
- Apple pages are dynamic and may change. If selectors break, update the locator in `monitor_pickup.py`.
- Respect Apple website terms and avoid aggressive scraping intervals.
