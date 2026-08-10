# cc-watcher

Watches [Cinema City Praha Flora](https://www.cinemacity.cz/) for new
70mm/IMAX screenings and sends a push notification via [ntfy.sh](https://ntfy.sh)
when one shows up. Runs for free on a schedule via GitHub Actions — no
server, no account, no API keys.

Built to track Christopher Nolan's *The Odyssey*, but works for any
70mm/IMAX screening at this cinema.

## How it works

Every 15 minutes, a GitHub Actions workflow:

1. Queries Cinema City's public JSON API for upcoming 70mm-tagged screenings
2. Compares them against the last known state (`state.json`, committed back
   to the repo each run)
3. Sends a push notification for anything new

**Currently alerts on:** new screenings appearing on the schedule.
*(Sold-out → available-again and seat-count-increase checks exist in the
code but are disabled — see `diff_states()` in `watcher.py` to re-enable.)*

The first run after setup only initializes state — it won't alert on
anything that's already on sale. Use `--force-report` for that.

## Setup

1. **Pick an ntfy topic** — a random, hard-to-guess string (e.g.
   `cc-imax-alerts-x7q2m9`). Anyone who knows it can read or post to it,
   so don't use anything guessable.
2. Subscribe to that topic in the [ntfy app](https://ntfy.sh/) (iOS/Android)
   or at `https://ntfy.sh/your-topic-name` in a browser.
3. Fork or clone this repo.
4. Add your topic as a repo secret: **Settings → Secrets and variables →
   Actions → New repository secret** → name it `NTFY_TOPIC`.
5. Make sure Actions is enabled: **Settings → Actions → General**.

## Testing

From the **Actions** tab → *Cinema City watcher* → **Run workflow**:

- Check **test_webhook** → sends one test notification, no API calls.
- Check **force_report** → reports everything currently on sale,
  ignoring saved state.

Or run locally:

```bash
pip install -r requirements.txt
export NTFY_TOPIC="your-topic-name"
python watcher.py --test-webhook
python watcher.py --force-report
```

## Configuration

Set as environment variables (or repo secrets) if you want to point this
at a different cinema or attribute:

| Variable | Default | Meaning |
|---|---|---|
| `NTFY_TOPIC` | — | required, your ntfy.sh topic |
| `CINEMA_ID` | `1052` | Cinema City Praha Flora |
| `ATTR` | `70-mm` | screening attribute to filter on |
| `HORIZON_DAYS` | `45` | how far ahead to check |

## Notes

- This uses Cinema City's unofficial public API — no guarantees it stays
  stable or doesn't rate-limit.
- GitHub disables scheduled workflows after 60 days of repo inactivity;
  not an issue here since each run commits `state.json`.
