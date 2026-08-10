#!/usr/bin/env python3
"""
Cinema City IMAX/70mm ticket watcher -> ntfy.sh push notifier.

Checks the Cinema City public JSON API for screenings matching a given
attribute (default: 70-mm) at a given cinema (default: 1052 = Praha Flora),
compares against the last known state, and pushes a notification via
ntfy.sh when:
  - a new matching screening appears
  - a sold-out screening becomes available again
  - the available-seat ratio increases

ntfy.sh needs no account or API key: pick a topic name, POST to
https://ntfy.sh/<topic>, and subscribe to that same topic in the ntfy
app on your phone (or via a browser) to receive push notifications.

Usage:
    python watcher.py                 # normal run: diff against state.json, alert on changes
    python watcher.py --force-report  # ignore state, report everything currently on sale
    python watcher.py --test-webhook  # send a single test notification, skip API entirely
    python watcher.py --seed          # just write current state, never send alerts

Environment variables:
    NTFY_TOPIC     required (except for --seed with no notification use)
    NTFY_SERVER    default "https://ntfy.sh"
    CINEMA_ID      default "1052"
    ATTR           default "70-mm"
    LANG           default "cs_CZ"
    HORIZON_DAYS   default "45"
    STATE_FILE     default "state.json"
"""

import json
import os
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://www.cinemacity.cz/cz/data-api-service/v1/quickbook/10101"


def cfg(name, default=None):
    return os.environ.get(name, default)


CINEMA_ID = cfg("CINEMA_ID", "1052")
ATTR = cfg("ATTR", "70-mm")
LANG = cfg("LANG", "cs_CZ")
HORIZON_DAYS = int(cfg("HORIZON_DAYS", "45"))
STATE_FILE = Path(cfg("STATE_FILE", "state.json"))
NTFY_TOPIC = cfg("NTFY_TOPIC", "jungs-watchen-cinema-city-prag-1!2!3!5")
NTFY_SERVER = cfg("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

HEADERS = {"User-Agent": "cc-watcher/1.0 (personal ticket-availability checker)"}


def get_json(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_dates():
    until = (date.today() + timedelta(days=HORIZON_DAYS)).isoformat()
    url = f"{BASE}/dates/in-cinema/{CINEMA_ID}/until/{until}?attr={ATTR}&lang={LANG}"
    data = get_json(url)
    return data.get("body", {}).get("dates", [])


def get_events_for_date(d):
    url = f"{BASE}/film-events/in-cinema/{CINEMA_ID}/at-date/{d}?attr={ATTR}&lang={LANG}"
    data = get_json(url)
    body = data.get("body", {})
    films = {f["id"]: f.get("name", "Unknown title") for f in body.get("films", [])}
    events = body.get("events", [])
    result = {}
    for ev in events:
        eid = ev.get("id")
        if not eid:
            continue
        result[eid] = {
            "filmName": films.get(ev.get("filmId"), ev.get("filmId", "Unknown")),
            "date": d,
            "time": ev.get("eventDateTime", ""),
            "auditorium": ev.get("auditorium", ""),
            "soldOut": bool(ev.get("soldOut", False)),
            "availabilityRatio": ev.get("availabilityRatio", 0) or 0,
            "bookingLink": (
                f"https://www.cinemacity.cz/cz/booking-router/launch/{eid}?lang=cs"
            ),
        }
    return result


def fetch_current_state():
    all_events = {}
    for d in get_dates():
        all_events.update(get_events_for_date(d))
    return all_events


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def diff_states(old, new, min_ratio_delta=0.002):
    """Return a list of structured alerts: {title, message, click, tags, priority}."""
    alerts = []
    for eid, ev in new.items():
        prev = old.get(eid)
        label = f"{ev['filmName']} — {ev['date']} {ev['time']} ({ev['auditorium']})"

        if prev is None:
            alerts.append({
                "title": "New IMAX/70mm screening",
                "message": label,
                "click": ev["bookingLink"],
                "tags": "new",
                "priority": "default",
            })
            continue

        if prev.get("soldOut") and not ev["soldOut"]:
            alerts.append({
                "title": "Tickets available again!",
                "message": label,
                "click": ev["bookingLink"],
                "tags": "tickets,rotating_light",
                "priority": "high",
            })
            continue

        delta = ev["availabilityRatio"] - prev.get("availabilityRatio", 0)
        if delta >= min_ratio_delta:
            alerts.append({
                "title": "More seats opened up",
                "message": f"{label} (+{delta:.1%} availability)",
                "click": ev["bookingLink"],
                "tags": "seat",
                "priority": "default",
            })

    return alerts


def post_to_ntfy(title, message, click=None, tags=None, priority="default"):
    if not NTFY_TOPIC:
        print(f"No NTFY_TOPIC set — skipping push. [{title}] {message}")
        return
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    headers = {"Title": title, "Priority": priority}
    if click:
        headers["Click"] = click
    if tags:
        headers["Tags"] = tags
    resp = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=15)
    resp.raise_for_status()


def send_test_message():
    post_to_ntfy(
        title="cc-watcher test",
        message="✅ If you see this, your ntfy topic is configured correctly "
                "and the workflow can reach it.",
        tags="white_check_mark",
    )
    print("Test notification sent (or printed above if no topic configured).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-report", action="store_true",
                         help="Report every current matching screening, ignoring saved state.")
    parser.add_argument("--seed", action="store_true",
                         help="Write current state to disk without sending any alerts.")
    parser.add_argument("--test-webhook", action="store_true",
                         help="Send a single test message to Discord and exit (no API calls).")
    args = parser.parse_args()

    if args.test_webhook:
        send_test_message()
        return

    print(f"Fetching current screenings for cinema {CINEMA_ID}, attr={ATTR} ...")
    new_state = fetch_current_state()
    print(f"Found {len(new_state)} matching screening(s).")

    old_state = load_state()
    first_run = not STATE_FILE.exists()

    if args.seed:
        save_state(new_state)
        print(f"Seeded {STATE_FILE} with {len(new_state)} screenings. No alerts sent.")
        return

    if args.force_report:
        alerts = [
            {
                "title": "Currently on sale" + (" (SOLD OUT)" if ev["soldOut"] else ""),
                "message": f"{ev['filmName']} — {ev['date']} {ev['time']} ({ev['auditorium']})",
                "click": ev["bookingLink"],
                "tags": "clipboard",
                "priority": "default",
            }
            for ev in new_state.values()
        ]
    elif first_run:
        print("No prior state found — initializing only, not sending alerts.")
        alerts = []
    else:
        alerts = diff_states(old_state, new_state)

    save_state(new_state)

    if not alerts:
        print("No changes to report.")
        return

    print(f"Sending {len(alerts)} alert(s) to ntfy...")
    for alert in alerts:
        post_to_ntfy(
            title=alert["title"],
            message=alert["message"],
            click=alert.get("click"),
            tags=alert.get("tags"),
            priority=alert.get("priority", "default"),
        )

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as e:
        print(f"HTTP error talking to Cinema City API: {e}", file=sys.stderr)
        sys.exit(1)
