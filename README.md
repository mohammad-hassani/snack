# TeamFlow

A runnable team chat MVP based on [prd.md](prd.md), with **Django 5.2 LTS + Django Channels** replacing the proposed Node backend. Django templates and plain JavaScript serve the frontend; no Node build step is needed.

## Language and direction

The interface is Persian and right-to-left by default, including authentication, dialogs, errors, and invitation/reset emails. Dates use the Persian calendar, and counts use Persian digits. Navigation mirrors on desktop and mobile; mixed Persian/English messages follow their text direction, while email addresses and links remain left-to-right. Existing names and conversations are preserved. Noto Sans Arabic fonts are served locally; their redistribution license is included in `static/chat/fonts/LICENSE.txt`.

## Run locally

Python 3.12+ is required.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000, create an account, and create a workspace. The development server supports WebSockets through Daphne. SQLite, local file storage, and the in-memory channel layer require no external services for a single local process.

Optional demo:

```sh
python manage.py seed_demo
```

The command prints a generated password. Sign in as `mina@teamflow.local`. It creates five demo accounts, channels, conversations, and sample messages. It never changes existing accounts and is disabled with `DEBUG=0`. For repeatable local browser checks, pass `--password` with a development-only password.

## Included

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

Open http://localhost:8000. Nginx serves static assets and proxies HTTP/WebSockets to Daphne; uploads are never served as public static files. PostgreSQL, uploads, and collected static assets use named volumes. Redis provides cross-process events, rate-limit counters, and presence. No database or Redis port is exposed to the host.

```sh
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo
docker compose exec web python manage.py test tests
```

`.env` is read by Docker Compose. When running Python directly, export variables into the shell; Django does not automatically load `.env`.

For production: use `DEBUG=0`, a random `SECRET_KEY`, explicit `ALLOWED_HOSTS` and HTTPS `CSRF_TRUSTED_ORIGINS`, SMTP, and PostgreSQL/Redis. Terminate TLS in a trusted proxy. The bundled Nginx listens on HTTP for local development. If TLS terminates upstream, configure trusted forwarded-protocol handling before enabling Django's HTTPS redirect; never trust arbitrary client-supplied forwarding headers. Use encrypted disks/backups and restrict access to persistent volumes.

## Verify

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test tests
node --check static/chat/app.js
```

The 18 tests cover account/workspace setup, access isolation, file authorization, duplicate-send protection, cursors, read positions, replies, edit/delete ownership, invitation identity/expiry/replay, final-admin protection, CSRF, WebSocket authentication/origin/session revocation, and backup restoration. A small load smoke opens 10 sockets and sends 20 messages (200 deliveries). Its printed p95 measures in-process ASGI latency, not network capacity or a production SLA.

Browser test (use a demo database only; it creates messages and a private channel):

```sh
pip install -r requirements-dev.txt
playwright install chromium
export TEAMFLOW_DEMO_PASSWORD='choose-a-local-test-password'
python manage.py seed_demo --password "$TEAMFLOW_DEMO_PASSWORD"
# In another terminal: python manage.py runserver
python scripts/browser_smoke.py
```

Set `TEAMFLOW_URL` for another server and optionally `CHROME_PATH` for an installed Chromium/Chrome binary. Screenshots are written to `artifacts/`. The browser test checks two-user live delivery, edits/deletes, reconnect, replies, uploads, search, private-channel visibility, direct messages, refresh persistence, JavaScript errors, and mobile overflow/navigation.

## Backup and restore

SQLite development backup, including uploaded files:

```sh
python scripts/backup.py /safe/location/teamflow-backup.tar.gz
```

This uses SQLite's online backup API, copies uploads, creates a SHA-256 manifest, restores into a temporary directory, and verifies every copied file and database integrity before reporting success. It refuses to overwrite an existing archive. For a coordinated database/file snapshot, pause writes while backing up; copying uploads during concurrent writes is not an atomic cross-storage snapshot.

To restore, stop Django, extract the archive into an **empty** directory, verify `manifest.json`, then move its `db.sqlite3` and `uploads/` into your app directory after preserving the current data. Do not unpack over a running database.

PostgreSQL deployment backup:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > teamflow.dump
```

Back up the uploads volume at the same maintenance point. Restore the dump with `pg_restore` into a new empty database, restore uploads, run migrations, then check message counts and authorized file downloads before switching traffic. Schedule encrypted off-host backups and regularly practice restoration.

## API and real-time protocol

All workspace and conversation endpoints require a session; all mutations require Django's CSRF token. JSON errors include an `error` field. IDs are integers. Channel history returns ascending messages in pages of 50.

| Endpoint | Method | Purpose |
|---|---|---|
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

Connect to `/ws/workspaces/{id}/` with the session cookie and a permitted Origin. Events use an `event` field. Send `send:message`, `edit:message`, `delete:message`, `start:typing`, `stop:typing`, or `read:message` with `channel_id` and event-specific fields. Send `ping` every 20 seconds. Server events include `ready`, `ack:message`, `new:message`, `updated:message`, `deleted:message`, `update:presence`, typing events, `pong`, and `error`. Authorization and session validity are rechecked on events, including before delivery. Reconnect clients fetch history from REST; database persistence happens before broadcast. Browser sends use REST (including attachments) and receive through WebSockets.

## Scope and remaining production work

This implements the PRD's first-phase MVP. Billing, subscriptions, calls, SSO, group DMs, emoji reactions, pinned messages, advanced threads/search, push/email message notifications, integrations, and enterprise audit/retention policies belong to later phases.

Known limits: the frontend is server-rendered instead of React/Next.js; search uses portable database substring queries; presence can take 45 seconds to expire; files use protected local storage instead of S3; uploads are validated but not malware-scanned; messages broadcast after commit without a transactional outbox (clients recover from durable history); background email queues and OpenTelemetry are not integrated. History restores missed sends and the latest 50 edits/deletions on reconnect; reload older history to refresh older mutations. Rate limits use the configured cache and the local fallback applies per process. PostgreSQL serializes sends per conversation; SQLite is intended for local use. Browser drafts live in session storage and attached files must be reselected after a reload. Load, TLS, email deliverability, encrypted infrastructure, and backup scheduling must be validated on the actual deployment before customer rollout.
