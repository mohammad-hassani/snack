# Next.js migration verification

The frontend is in `frontend/`. Django remains the authority for authentication,
authorization, validation, storage, REST, and WebSockets. Checks below use the real
local backend, SQLite, and the in-memory Channels layer, without mocked services.

## Automated checks

- `python manage.py test tests`: 23 tests passed. Covers API validation, CSRF,
  sessions and account lifecycle, workspace isolation, public/private channels,
  messages, duplicate sends, cursors, read positions, ownership, attachments,
  invitation identity/expiry/replay, final-admin protection, password reset tokens,
  WebSocket authentication/origin/session revocation, and backup restoration.
- The same suite's ASGI smoke: 10 sockets, 20 sends, 200 deliveries. This tests
  local delivery, not production capacity.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no model changes.
- `npm run build --prefix frontend`: production build passed.
- `npm audit --prefix frontend`: zero known vulnerabilities at verification time.
- `git diff --check`: passed.
- `docker compose --env-file .env.example config --no-env-resolution --quiet`: configuration validation passed.

## Real browser checks

Run both servers, install `requirements-dev.txt`, and install Chromium with
`playwright install chromium`, or set `CHROME_PATH` to an installed Chrome binary.
These tests write demo content; use a development database only.

```sh
export SNACK_DEMO_PASSWORD='choose-a-local-test-password'
python manage.py seed_demo --password "$SNACK_DEMO_PASSWORD"
python scripts/browser_smoke.py
python scripts/browser_accounts.py
```

`SNACK_URL` defaults to `http://127.0.0.1:3000`. Both suites passed against the
production Next.js server and real Django backend in Chrome:

- Chat: two-user live delivery, edit/delete, reconnect recovery, replies, uploads,
  search, private-channel isolation, DM, persistence, Persian RTL layout, mobile
  overflow and navigation; no JavaScript errors. Screenshots: ignored `artifacts/`.
- Accounts: signup, workspace onboarding, final-admin guard, invitation followed
  through signup and acceptance, member permissions, live delivery, logout,
  rejected credentials, password-reset request, safe login redirects; no JavaScript errors.

## Postman live checks

The Postman API engineering and API testing skills were used. CLI requests ran
locally with `--no-report-events`; nothing was published to a Postman workspace.
Four assertions passed across three live requests:

- Django `/health/`: HTTP 200 and `status: ok` (CLI exit 0).
- Next.js `/api/session/`: anonymous state, CSRF token, and `no-store` (two tests,
  CLI exit 0).
- Next.js `/api/workspaces/`: JSON 401 without authentication (assertion passed;
  this CLI returns exit 1 for the intentional non-2xx HTTP response).

The repeatable Django suite provides the authenticated mutation and negative API
coverage; the browser suites prove those APIs through the Next.js proxy.

## Limits

Docker/Nginx/PostgreSQL/Redis integration was configured but not executed because
the Docker daemon was stopped. Real SMTP delivery, HTTPS termination, deployment
and production load were not verified. Local reset/invitation emails use Django's
console backend. Django page URLs on port 8000 redirect to Next.js when `FRONTEND_URL` is set;
the Next.js app is the user entry point on port 3000 (Docker: 8000).

## Snack rename verification

The Django package, frontend/package lock, UI and email branding, environment
variables, demo emails, docs, and business-plan filename/content now use Snack.
The five local demo accounts were renamed to `@snack.local` without changing
password hashes, memberships, messages, or uploaded files. A verified database
and upload backup was saved to ignored `artifacts/before-snack-rename.tar.gz`.

The 23 Django tests, Next.js production build, chat browser suite, account browser
suite, Docker Compose configuration validation, and `git diff --check` passed
after the rename. `node frontend/lib/storage.test.mjs` verifies browser draft,
retry ID, and channel-preference migration, including conflicts and repeat runs.
The old product name remains only in that compatibility code and its test.

The PDF contains 12 Snack references across 11 pages. Text assertions confirm
that all old product references were removed and surrounding text was preserved.
Existing sessions may need a fresh login because the default development signing
key was renamed. Docker runtime and real SMTP remain unverified.

## Dark theme verification

`npm run build --prefix frontend` and `scripts/browser_theme.py` passed against
the real app. The browser check verifies device defaults, keyboard toggle,
saved preference across reload/login navigation, dark chat/search/dialog surfaces,
mobile overflow and toggle spacing, and operation when local storage is blocked.
No JavaScript errors were reported. Screenshots are in ignored
`artifacts/theme-dark-{login,workspace,mobile}.png`. The check defaults to the
local `admin` / `admin` account; set `SNACK_ADMIN_USERNAME` and
`SNACK_ADMIN_PASSWORD` for another development account. Backend tests were not
rerun for this frontend-only change.

## Dashboard entry-point regression

Port 8000 served the legacy Django dashboard without the theme toggle. Django
now redirects page GET/HEAD requests to `FRONTEND_URL`, preserving paths and
query strings, while APIs, files, static assets, and admin stay on Django.
All 27 Django tests passed, including routing and fallback tests. The theme
browser suite also passed with `SNACK_URL=http://127.0.0.1:8000`, verifying the
old entry point reaches the current dashboard with a working theme toggle.

## Lucide icon verification

The Next.js UI uses `lucide-react` 1.61.0 for navigation, channel visibility,
search, formatting, attachments, message actions, dialogs, branding, and theme
controls. Icons are decorative SVGs with labels retained on their controls.
The emoji picker still inserts actual emoji into messages.

The production build, icon browser suite, and theme browser suite passed.
`python scripts/browser_icons.py` checks SVG rendering, accessible controls,
formatting, dialogs, theme switching, and desktop/mobile navigation. Screenshots
are in ignored `artifacts/icons-*.png`. Dependency installation audited 24
packages with zero known vulnerabilities. Backend tests were not rerun for
this UI-only change.
