# dmj-vault

Simple API Keys Vault — issue API keys with scoped permissions, validate them via a `/check` endpoint.

## Packages

| Package | Description |
|---------|-------------|
| `dmj-vault-dbserver` | MySQL database setup (`DMJ_VAULT`), schema migrations, admin account CLI |
| `dmj-vault-dbaccess` | Peewee ORM models (depends on dbserver) |
| `dmj-vault-apps-admin` | Flask JSON API for managing keys (gunicorn, 127.0.0.1:9701) |
| `dmj-vault-apps-api` | FastAPI `/check` endpoint (gunicorn + nginx, 127.0.0.1:9800) |

## Installation

All packages are installed on the same machine by design:

```bash
sudo apt install dmj-vault-*.deb
```

## Post-install setup

Set the admin account (run once after installing `dmj-vault-dbserver`):

```bash
sudo dmj-vault-set-admin-account
```

This sets the login and hashed password in the `ADMIN` table. The default password value (`*`) blocks all login attempts until this command is run.

## Admin API (`dmj-vault-apps-admin`)

Listens on `127.0.0.1:9701` by default. All routes except `/login` require an active session.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | POST | `{"login": "...", "password": "..."}` |
| `/logout` | POST | Clears session |
| `/api-keys` | GET | List all API keys |
| `/api-keys` | POST | Create key: `{"permissions": {"scope": "read\|write"}, "ts_expires": null}` |
| `/api-keys/<uid>` | GET | Key detail with whitelist |
| `/api-keys/<uid>/update` | POST | Update `is_valid`, `ts_expires`, `permissions` |
| `/api-keys/<uid>/delete` | POST | Delete key and its whitelist entries |
| `/api-keys/<uid>/whitelist/add` | POST | `{"src_ip_address": "1.2.3.4"}` |
| `/api-keys/<uid>/whitelist/<id>/delete` | POST | Remove whitelist entry |

New keys are created with `is_valid=0`. Activate them with `/api-keys/<uid>/update`.

## Vault API (`dmj-vault-apps-api`)

Exposed via nginx on `127.0.0.1:9800` by default.

### `POST /check`

```json
{
  "api_key": "<uid>",
  "scope": "myservice",
  "access_type": "read"
}
```

Returns `{"valid": true}` on success, or HTTP 403/404 with a `detail` message.

Validation order:
1. Key exists in `API_KEY` table (404 if not)
2. `is_valid=1` and not expired (403 if not)
3. If IP whitelist entries exist for this key, client IP must be in the list (403 if not)
4. `scope` present in permissions; `"write"` grants both read and write; `"read"` grants read only (403 if insufficient)

## Configuration

Both services read a key=value config file with `conf.d` drop-in support.

**Admin app:** `/etc/dmj-vault-apps-admin/conf` and `/etc/dmj-vault-apps-admin/conf.d/*.conf`

```
PORT=9701
HOST=127.0.0.1
WORKERS=2
```

**API app:** `/etc/dmj-vault-apps-api/conf` and `/etc/dmj-vault-apps-api/conf.d/*.conf`

```
GUNICORN_PORT=9702
GUNICORN_HOST=127.0.0.1
GUNICORN_WORKERS=4
NGINX_PORT=9800
NGINX_HOST=127.0.0.1
```

## Service management

Reload gunicorn workers gracefully (picks up code changes, no dropped connections):

```bash
systemctl reload dmj-vault-apps-admin
systemctl reload dmj-vault-apps-api
```

Apply `PORT`/`HOST` config changes (requires restart):

```bash
systemctl restart dmj-vault-apps-admin
systemctl restart dmj-vault-apps-api
```

Apply nginx config changes (`NGINX_PORT`/`NGINX_HOST`):

```bash
# Edit /etc/dmj-vault-apps-api/conf, then:
sudo dmj-vault-apps-api-nginx-update
```

This rewrites `/etc/nginx/sites-available/dmj-vault-apps-api` from the current config and reloads nginx.

## Building packages

```bash
sudo apt-get install devscripts dpkg-dev debhelper dh-python \
  pybuild-plugin-pyproject python3-all python3-setuptools

chmod +x packaging/build_deb.sh
./packaging/build_deb.sh all
# Output: /tmp/dmj-vault-packages/
```

Build a single package:

```bash
./packaging/build_deb.sh dmj-vault-dbserver
```
