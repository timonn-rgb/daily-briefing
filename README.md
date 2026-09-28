# Daily Briefing

A daily world-news and stock-market briefing. Each morning it collects headlines and
market data, has Claude write a short summary, publishes a page on GitHub Pages, and
emails it out.

## How it runs

A GitHub Actions workflow (`.github/workflows/daily.yml`) produces the briefing.

- **Main trigger:** a cron-job.org job calls GitHub's API at **06:10 Berlin time** to start
  the workflow (`workflow_dispatch` with `force=false`). It uses a fine-grained GitHub token
  that can only run this repo's workflows (it expires; see Maintenance).
- **Backup:** GitHub's own schedule (04:15 and 05:15 UTC). GitHub often starts these
  hours late, so `briefing.gate` accepts any run from 06:00 to 15:59 Berlin time
  (`send_hour` / `send_until_hour` in `config.yaml`) and skips once today's email was sent.
  You get at most one briefing a day.

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

- Before the cron-job.org token expires: create a new fine-grained GitHub token
  (this repo only, permission Actions: read and write) and paste it into the
  cron-job.org job's `Authorization: Bearer …` header. If briefings start arriving
  around midday instead of ~06:15, the token or the cron-job.org job is the first
  thing to check (the job's history shows GitHub's response; it should be 204).
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
