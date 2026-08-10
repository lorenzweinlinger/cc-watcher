# cc-watcher

Watches Cinema City Praha Flora for new 70mm/IMAX screenings and ticket
availability changes, and sends you a push notification via ntfy.sh.
Runs for free on a schedule via GitHub Actions — no server of your own,
no account signup, no API keys required.

## Setup

1. **Pick a topic name.** ntfy.sh has no accounts — a "topic" is just a
   URL path that acts like a private channel. Anyone who knows the exact
   topic name can subscribe to it or post to it, so pick something long
   and hard to guess, e.g. `cc-imax-alerts-x7q2m9` rather than
   `my-alerts`. Do NOT use a short/guessable name for anything sensitive.

2. **Get the ntfy app** on your phone (iOS/Android, free, from ntfy.sh)
   or just open `https://ntfy.sh/your-topic-name` in a browser. Subscribe
   to your topic name from step 1. That's the entire "account setup" —
   nothing to register, no login.

3. **Create a new GitHub repo** (public, so Actions minutes are
   unlimited) and push these files to it.

4. **Add your topic as a repo secret**: GitHub repo → Settings → Secrets
   and variables → Actions → New repository secret → name it
   `NTFY_TOPIC`, paste your topic name (just the name, not the full URL).

5. **Enable Actions** if it's not already: Settings → Actions → General
   → allow workflows to run.

## Testing before you rely on it

Don't just wait for the cron job — test it explicitly:

- **Test the notification only** (no API calls, just confirms ntfy will
  reach your phone): go to the Actions tab → "Cinema City watcher" →
  Run workflow → check "test_webhook" → Run. You should get a push
  notification within a few seconds — if the ntfy app isn't open, it
  should still arrive since ntfy.sh delivers via each platform's native
  push service once subscribed.

- **Test the full pipeline against real data**: Run workflow → check
  "force_report" → Run. This reports every currently-on-sale matching
  screening, ignoring saved state, so you should see real results
  (or "No changes to report" if nothing is on sale right now).

- **Test locally** (optional, needs Python 3.11+):
  ```bash
  pip install -r requirements.txt
  export NTFY_TOPIC="your-topic-name"
  python watcher.py --test-webhook     # just pings ntfy
  python watcher.py --force-report     # shows everything currently on sale
  python watcher.py --seed             # initializes state.json quietly
  python watcher.py                    # normal run: only alerts on changes
  ```

## Normal operation

Once confirmed working, just leave it — the workflow runs every 15
minutes automatically, diffs against the last saved `state.json`
(committed back to the repo each run), and only messages you when
something actually changes: a new screening appears, a sold-out show
opens back up, or more seats become available.

## Notes

- Change `CINEMA_ID`, `ATTR`, `HORIZON_DAYS` etc. as env vars in the
  workflow file if you want to watch a different cinema or attribute.
- GitHub disables scheduled workflows after 60 days with no repo
  activity — not an issue here since each run commits `state.json`.
- If you ever see 0 results even with `--force-report`, it likely means
  tickets for the horizon window just haven't been released yet (Cinema
  City tends to release ~1 week at a time, often Tuesday mornings).
