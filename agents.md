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
