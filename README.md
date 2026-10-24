# Snack

A runnable team chat MVP based on [prd.md](prd.md), with **Django 5.2 LTS + Django Channels** replacing the proposed Node backend. The frontend is Next.js 16 + React 19 (App Router); Django owns JSON APIs, session authentication, permissions, persistence, protected uploads, email, and Channels WebSockets.

## Language and direction

The interface is Persian and right-to-left by default, including authentication, dialogs, errors, and invitation/reset emails. Dates use the Persian calendar, and counts use Persian digits. Navigation mirrors on desktop and mobile; mixed Persian/English messages follow their text direction, while email addresses and links remain left-to-right. Existing names and conversations are preserved. The supplied IRANYekanXFaNum fonts are served locally from `static/chat/fonts/`, using Regular, Medium, DemiBold, Bold, and ExtraBold weights.

## Run locally

Python 3.12+ and Node.js 20.9+ are required.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000, create an account, and create a workspace. Next.js proxies `/api/`, `/ws/`, `/files/`, `/admin/`, `/health/`, and shared `/static/` assets to Django at `127.0.0.1:8000`, keeping cookies and CSRF on one browser origin. Set `DJANGO_URL` for a different backend. Django trusts localhost port 3000 for CSRF only in debug mode. `FRONTEND_URL` defaults to `http://127.0.0.1:3000` locally and controls invitation/password-reset links. The Django development server supports WebSockets through Daphne. SQLite, local file storage, and the in-memory channel layer require no external services for a single local process.

Optional demo:

```sh
python manage.py seed_demo
```

The command prints a generated password. Sign in as `mina@snack.local`. It creates five demo accounts, channels, conversations, and sample messages. It never changes existing accounts and is disabled with `DEBUG=0`. For repeatable local browser checks, pass `--password` with a development-only password.

## Included

- Light/dark theme toggle on every Next.js page (sun/moon button at the top left). First visit follows the device theme; an explicit choice is saved locally and applied before the page paints.

- Email/password registration and sign-in, POST logout, session authentication, password reset.
- Multiple workspaces, email-bound invitations expiring after seven days, admin/member roles, member removal, and protection against removing the final admin.
- Public channels, private channels with selected members, and unique one-to-one direct conversations.
- Persistent messages with replies, edit/delete permissions, stable IDs, idempotent retries, and cursor pagination.
- WebSocket delivery and acknowledgments, reconnect history recovery, typing indicators, heartbeat presence, unread counts, and in-app activity.
- Protected file downloads; files up to 10 MB; extension allowlist and image validation. Deleted-message files cannot be downloaded.
- Search scoped to authorized conversations. Responsive UI, keyboard controls, Unicode/Persian message content, visible focus styles.
- Django admin at `/admin/` and database health at `/health/`.
- Migrations, automated API/WebSocket tests, browser smoke checks, SQLite backup/restore verification, PostgreSQL/Redis Docker configuration.

Create a global Django administrator with `python manage.py createsuperuser`. Workspace administrators manage only their own workspace through the app; global staff access is separate.

## Email

Development emails print to the server console, including invitations and password reset links. An admin can also copy an invitation link from the app. Invitees create an account with the invited email, open the link, and explicitly accept it.

For actual delivery, configure `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`. Email is sent synchronously in this MVP. A failed invitation delivery returns an error; delivery is never reported as successful when SMTP fails.

## Docker: PostgreSQL and Redis

```sh
cp .env.example .env
# Edit the database password and application secret.
docker compose up --build -d
```

Open http://localhost:8000. Nginx serves static assets, routes user pages to Next.js, and routes APIs, protected files, admin, health, and WebSockets to Daphne; uploads are never served as public static files. PostgreSQL, uploads, and collected static assets use named volumes. Redis provides cross-process events, rate-limit counters, and presence. No database or Redis port is exposed to the host.

```sh
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py test tests
```

`.env` is read by Docker Compose. When running Python directly, export variables into the shell; Django does not automatically load `.env`.

For production: use `DEBUG=0`, a random `SECRET_KEY`, explicit `ALLOWED_HOSTS`, HTTPS `CSRF_TRUSTED_ORIGINS` and `FRONTEND_URL`, SMTP, and PostgreSQL/Redis. Terminate TLS in a trusted proxy. The bundled Nginx listens on HTTP for local development. If TLS terminates upstream, configure trusted forwarded-protocol handling before enabling Django's HTTPS redirect; never trust arbitrary client-supplied forwarding headers. Use encrypted disks/backups and restrict access to persistent volumes.

## Verify

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tests
npm ci --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend
```

The Django tests cover account/workspace setup, access isolation, file authorization, duplicate-send protection, cursors, read positions, replies, edit/delete ownership, invitation identity/expiry/replay, final-admin protection, CSRF, WebSocket authentication/origin/session revocation, and backup restoration. A small load smoke opens 10 sockets and sends 20 messages (200 deliveries). Its printed p95 measures in-process ASGI latency, not network capacity or a production SLA.

Browser test (use a demo database only; it creates messages and a private channel):

```sh
pip install -r requirements-dev.txt
playwright install chromium
export SNACK_DEMO_PASSWORD='choose-a-local-test-password'
python manage.py seed_demo --password "$SNACK_DEMO_PASSWORD"
# Keep Django (8000) and Next.js (3000) running in separate terminals.
python scripts/browser_smoke.py
python scripts/browser_accounts.py
python scripts/browser_theme.py
```

Set `SNACK_URL` for another server and optionally `CHROME_PATH` for an installed Chromium/Chrome binary. Screenshots are written to `artifacts/`. Run `python scripts/browser_accounts.py` as well to check signup, onboarding, invitation acceptance through signup, member permissions, logout, invalid login, and password-reset requests. These browser scripts create accounts and messages; use a development database only. Set `CHROME_PATH` when running them with an installed Chrome binary.

The browser test defaults to Next.js on port 3000 and checks two-user live delivery, edits/deletes, reconnect, replies, uploads, search, private-channel visibility, direct messages, refresh persistence, JavaScript errors, and mobile overflow/navigation.

## Backup and restore

SQLite development backup, including uploaded files:

```sh
python scripts/backup.py /safe/location/snack-backup.tar.gz
```

This uses SQLite's online backup API, copies uploads, creates a SHA-256 manifest, restores into a temporary directory, and verifies every copied file and database integrity before reporting success. It refuses to overwrite an existing archive. For a coordinated database/file snapshot, pause writes while backing up; copying uploads during concurrent writes is not an atomic cross-storage snapshot.

To restore, stop Django, extract the archive into an **empty** directory, verify `manifest.json`, then move its `db.sqlite3` and `uploads/` into your app directory after preserving the current data. Do not unpack over a running database.

PostgreSQL deployment backup:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > snack.dump
```

Back up the uploads volume at the same maintenance point. Restore the dump with `pg_restore` into a new empty database, restore uploads, run migrations, then check message counts and authorized file downloads before switching traffic. Schedule encrypted off-host backups and regularly practice restoration.

## API and real-time protocol

All workspace and conversation endpoints require a Django session cookie (unauthenticated API calls return JSON 401); all mutations require Django's CSRF token. API errors include an `error` field; form validation may also include a `fields` map. APIs return 400 for invalid input, 403 for denied access/CSRF, 404 for missing resources, 405 for invalid methods, and 409 for conflicting names. Authenticated API responses are never cached. IDs are integers. Channel history returns ascending messages in pages of 50.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/session/` | GET | User or `null`, accessible workspaces, `csrfToken`; sets CSRF cookie |
| `/api/auth/signup/` | POST | `first_name`, `email`, `password1`, `password2`; creates account/session (201) |
| `/api/auth/login/` | POST | `username` (email), `password`; creates session, returns rotated CSRF token |
| `/api/auth/logout/` | POST | Invalidates current session |
| `/api/auth/password-reset/` | POST | `email`; same 200 response for existing/unknown email |
| `/api/auth/reset/{uidb64}/{token}/` | POST | `new_password1`, `new_password2`; validates single-use reset token |
| `/api/workspaces/` | GET / POST | Lists accessible teams; POST `name` creates workspace and default channels (201) |
| `/api/invites/{token}/` | GET / POST | Preview or explicitly accept unexpired invitation for signed-in email |
| `/api/workspaces/{id}/` | GET | Current user, accessible channels, unread counts, members/presence |
| `/api/workspaces/{id}/channels/` | POST | Create public/private channel with optional member IDs |
| `/api/workspaces/{id}/direct/` | POST | Create or reuse a DM using `user_id` |
| `/api/workspaces/{id}/invites/` | POST | Invite `email` (workspace admin) |
| `/api/workspaces/{id}/members/{user_id}/` | POST | Set `role` to `admin`, `member`, or `remove` |
| `/api/workspaces/{id}/search/?q=...` | GET | Search authorized messages, up to 50 results |
| `/api/channels/{id}/messages/` | GET | History, optional `before` or `after` message ID |
| `/api/channels/{id}/messages/` | POST | Send JSON or multipart `body`, UUID `client_message_id`, optional `reply_to` and `file` |
| `/api/messages/{id}/` | PATCH / DELETE | Edit body / soft-delete message |
| `/api/channels/{id}/read/` | POST | Advance `message_id` read position |
| `/files/{id}/` | GET | Authorized attachment download |

For JSON mutations send `Content-Type: application/json` and `X-CSRFToken` from `/api/session/` (or the current `csrftoken` cookie). Refresh the token after login/signup because Django rotates it. Login, signup, reset, logout, and multipart uploads all retain CSRF protection. Use multipart form data only for file sends; include the same CSRF header. Browser cookies are HttpOnly for sessions, SameSite=Lax, and Secure when `DEBUG=0`.

For a production frontend build use `cd frontend && npm run build && npm start`; keep Django/Daphne running separately. The Docker stack builds both applications and exposes only Nginx at port 8000.

Connect to `/ws/workspaces/{id}/` with the session cookie and a permitted Origin. Events use an `event` field. Send `send:message`, `edit:message`, `delete:message`, `start:typing`, `stop:typing`, or `read:message` with `channel_id` and event-specific fields. Send `ping` every 20 seconds. Server events include `ready`, `ack:message`, `new:message`, `updated:message`, `deleted:message`, `update:presence`, typing events, `pong`, and `error`. Authorization and session validity are rechecked on events, including before delivery. Reconnect clients fetch history from REST; database persistence happens before broadcast. Browser sends use REST (including attachments) and receive through WebSockets.

## Scope and remaining production work

This implements the PRD's first-phase MVP. Billing, subscriptions, calls, SSO, group DMs, emoji reactions, pinned messages, advanced threads/search, push/email message notifications, integrations, and enterprise audit/retention policies belong to later phases.

When `FRONTEND_URL` is set, old Django page URLs redirect to the Next.js interface while preserving the path and query string. The original templates remain as a fallback when `FRONTEND_URL` is empty. Shared CSS and local Persian fonts are reused by both.

Known limits: search uses portable database substring queries; presence can take 45 seconds to expire; files use protected local storage instead of S3; uploads are validated but not malware-scanned; messages broadcast after commit without a transactional outbox (clients recover from durable history); background email queues and OpenTelemetry are not integrated. History restores missed sends and the latest 50 edits/deletions on reconnect; reload older history to refresh older mutations. Rate limits use the configured cache and the local fallback applies per process. PostgreSQL serializes sends per conversation; SQLite is intended for local use. Browser drafts live in session storage and attached files must be reselected after a reload. Load, TLS, email deliverability, encrypted infrastructure, and backup scheduling must be validated on the actual deployment before customer rollout.
