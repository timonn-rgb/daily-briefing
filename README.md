# Daily Briefing

A daily world-news and stock-market briefing. Each morning it collects headlines and
market data, has Claude write a short summary, publishes a page on GitHub Pages, and
emails it out.

## How it runs

A GitHub Actions workflow (`.github/workflows/daily.yml`) runs on a schedule and
targets 06:15 Berlin time (it fires twice, at 04:15 and 05:15 UTC, so one of the two
runs lands in the right local hour whether Berlin is on CEST or CET; `briefing.gate`
decides which run, if either, actually produces an edition).

Each run: collects news and market data, asks Claude to write the summary (with one
retry if the first attempt is unusable), renders the web page and email, commits the
new `data/` and `site/` files, publishes to GitHub Pages, and sends the email.

### Run it manually

Go to the repo's **Actions** tab → **Daily Briefing** → **Run workflow**. The `force`
input defaults to `true`, so a manual run produces and sends an edition immediately,
even outside the send window, even if today's edition was already sent, and even
while the schedule is disabled in `config.yaml`.

### Run it locally (dry run)

```
python -m scripts.dry_run             # uses your local `claude` login
python -m scripts.dry_run --no-claude # skip the AI step, preview the raw edition
```

This collects data and renders the page and email into `build/`, without publishing
or emailing anything, and opens the results in your browser.

## Settings

All feeds, tickers, and behavior live in `config.yaml` — change things there, not in
code. Notably:

- `schedule_enabled` — the scheduled workflow is a no-op until this is `true`. Leave
  it `false` while testing with manual/forced runs, then flip it on once a few manual
  runs look good.
- `model` — must match the `--model` flag used in `.github/workflows/daily.yml`.
- `site_base_url` — the published GitHub Pages URL, used in email links.

## Secrets

Set these in the repo's Settings → Secrets and variables → Actions:

- `CLAUDE_CODE_OAUTH_TOKEN` — from `claude setup-token`, used by the Claude Code
  Action to write the briefing.
- `GMAIL_ADDRESS` — the Gmail account the briefing is sent from.
- `GMAIL_APP_PASSWORD` — a Gmail app password for that account (not your normal
  password).
- `BRIEFING_TO` — the address(es) the briefing is sent to.

`GITHUB_TOKEN` is provided automatically by Actions; it doesn't need to be set.

## Maintenance

- Every few months: `python -m scripts.update_sp500` to refresh the list of S&P 500
  constituents used for the movers section.
- If the page shows a "Limited sources today" banner regularly: run
  `python -m scripts.check_feeds` to see which configured RSS feeds are failing, and
  fix or drop them in `config.yaml`.
- If GitHub disables the workflow for repository inactivity, re-enable it from the
  Actions tab (Actions → Daily Briefing → "..." → Enable workflow).
- If every day starts coming through as a raw edition (no AI summary), the Claude
  Code OAuth token has likely expired — run `claude setup-token` again and update the
  `CLAUDE_CODE_OAUTH_TOKEN` secret.
