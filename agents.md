# Agent Instructions — World Inflation Tracker

## Server Access

- **Server IP:** `157.245.60.144`
- **User:** `master_pnjkjbpsxn`
- **SSH key:** `wit_deploy_key` (ed25519) located at `/c/Users/User/OneDrive - Sumathi Holdings/Desktop/WIT/wit_deploy_key`
- **Public key:** `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINpil9gFhBdb6R8tOD46iz2BW1StYiVxG1JHbIcsr8Nk wit-deploy-key`
- This key is authorized on the server and should be used for all SSH operations.

## Critical Port Rules

- **WIT / Gunicorn runs on port `8000`.** Always use `127.0.0.1:8000` in `index.php`, `startup.sh`, `watchdog_gunicorn.sh`, and Nginx/proxy configs.
- **NEVER touch port `8001`.** It is used by another application on the same server.

## Deployment Path

```text
/home/master/applications/ctaaqxskeb/public_html
```

Always run Git pulls, migrations, and management commands from this directory.

## Important Reminders

- Read `memory.md` and `agents.md` at the start of every new context window.
- When editing files, append rather than overwrite whenever possible.
- Do not run `git commit`, `git push`, `git reset`, or `git rebase` without explicit user confirmation.

## Deployment Verification — 2026-07-06

- SSH key `wit_deploy_key` is working on the server.
- Latest code deployed to `/home/master/applications/ctaaqxskeb/public_html`.
- Migrations applied successfully.
- Gunicorn restarted and responding on **port 8000**.
- Public site `https://worldinflationtracker.com/` returns HTTP 200.

## Working Scrapers

- `python3 manage.py scrape_configured_sources --country LKA --source Spar` ✅
- `python3 manage.py scrape_configured_sources --country LKA --source CEYPETCO` ✅

## Keells / Playwright Blocker

- Keells is configured to use Playwright but the server is missing system browser dependencies.
- Do **not** run `sudo` commands; ask the user/Cloudways support to install them.
- Required packages: `libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libatspi2.0-0 libxcomposite1 libxdamage1`
- After installation: `python3 -m playwright install chromium`

## Reminder

- WIT runs on **port 8000** only. Never touch **port 8001**.
