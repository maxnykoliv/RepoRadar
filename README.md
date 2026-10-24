# RepoRadar

[![CI](https://github.com/maxnykoliv/RepoRadar/actions/workflows/ci.yml/badge.svg)](https://github.com/maxnykoliv/RepoRadar/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-blue)
![Django](https://img.shields.io/badge/Django-5.2-092E20)
![React](https://img.shields.io/badge/React-18-61DAFB)
![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen)

Search GitHub repositories and keep a personal list of favorites.

A **Django REST Framework** API sits in front of the [GitHub Search API](https://docs.github.com/en/rest/search),
caches results in **Redis** and translates GitHub's failure modes into clear HTTP
errors. JWT-authenticated users can save repositories to their favorites. A
**React + Vite** client covers the whole flow.

## Highlights

- **Caching that can't take the service down:** normalized cache keys with a 2-hour TTL. If Redis is unavailable, search keeps working uncached instead of returning errors.
- **Upstream errors mapped precisely:** GitHub's rate limits become `429` with a `Retry-After` header, rejected queries become `422`, and outages and timeouts become `502` and `504`, never a generic `500`.
- **Race-safe favorites:** duplicates are rejected by a database unique constraint (`409`), not by a check-then-insert that two concurrent requests could both pass.
- **Auth:** JWT access and refresh tokens (SimpleJWT), Django's password validators, and case-insensitive unique emails.
- **Tested against real infrastructure in CI:** 53 tests at 97% coverage. They include Redis integration tests, a migrations-in-sync check and OpenAPI schema validation, plus frontend and Docker builds.

## Tech stack

| Layer | Choice |
|---|---|
| API | Django 5.2, Django REST Framework, drf-spectacular (OpenAPI) |
| Auth | djangorestframework-simplejwt |
| Cache | Redis via django-redis |
| Database | SQLite (favorites and users) |
| Frontend | React 18, Vite, axios |
| Serving | gunicorn + whitenoise; nginx for the built client |
| Tooling | Docker Compose, GitHub Actions, ruff, coverage.py |

## Quick start

```bash
cp .env.example .env
# set DJANGO_SECRET_KEY, e.g. python -c "import secrets; print(secrets.token_urlsafe(50))"
# optionally set GITHUB_TOKEN to raise GitHub's search limit from 10 to 30 requests/min

docker compose up --build
```

| URL | |
|---|---|
| http://localhost:5173 | React client |
| http://localhost:8000/api/docs/ | Swagger UI |
| http://localhost:8000/admin/ | Django admin |

To use the admin or clear the cache, create a staff account:

```bash
docker compose exec api python manage.py createsuperuser
```

## API

### Search

`POST /api/search`

```json
{ "type": "repositories", "query": "django rest", "page": 1, "per_page": 30 }
```

`type` is one of `users`, `repositories` or `issues`. `page` defaults to 1 and
`per_page` defaults to 30 (maximum 100). GitHub only serves the first 1000
results, so `page * per_page` must be at most 1000.

```json
{ "type": "repositories", "query": "django rest", "page": 1, "per_page": 30,
  "cached": false, "total_count": 123, "incomplete_results": false, "items": [ ... ] }
```

`items` are GitHub's objects, unchanged. `cached` tells you whether GitHub was
called.

| Status | Meaning |
|---|---|
| `400` | Invalid body: missing, blank or too long query, unknown type, or bad pagination |
| `422` | GitHub rejected the query |
| `429` | GitHub rate limit hit; the `Retry-After` header is set |
| `502` / `504` | GitHub was unreachable, timed out or returned garbage |

### Auth

| Method | Path | |
|---|---|---|
| POST | `/api/auth/register/` | `{username, email, password}` → `201` |
| POST | `/api/auth/login/` | `{username, password}` → `{access, refresh}` |
| POST | `/api/auth/refresh/` | `{refresh}` → `{access}` |

### Favorites (JWT required)

| Method | Path | |
|---|---|---|
| GET | `/api/favorites/` | The current user's favorites, newest first |
| POST | `/api/favorites/` | Save `{repo_id, full_name, html_url, description, stargazers_count, forks_count, language}` → `201`, or `409` if already saved |
| DELETE | `/api/favorites/{repo_id}/` | `204`, or `404` if the repo isn't in *your* favorites |

### Cache maintenance (staff only)

`POST|DELETE /api/clear-cache` removes all cached search results and returns `{"detail": "...", "deleted": <n>}`.

## Design decisions

- **Layers:** `views` (HTTP) → `services` (cache and orchestration) → `github_client` (HTTP to GitHub). Each layer is tested on its own, and GitHub is mocked at the client boundary.
- **Cache key:** a SHA-256 of `(type, normalized lower-cased query, page, per_page)`. GitHub search is case-insensitive, so `"Foo  Bar"` and `" foo bar "` share an entry.
- **What is never cached:** errors, and responses with `incomplete_results: true` (GitHub timed out internally and returned partial data).
- **Targeted invalidation:** clearing the cache uses `delete_pattern("search:*")`, so other keys in the same Redis survive. `FLUSHDB` would be too destructive. An integration test against real Redis checks this.
- **Degrade, don't fail:** with `IGNORE_EXCEPTIONS`, a Redis outage turns cache operations into misses.
- **A plain `403` is not a rate limit:** GitHub uses `403` for both. A request counts as rate-limited only when `X-RateLimit-Remaining: 0`, `Retry-After` or a rate-limit message is present.
- **Clear-cache is staff-only:** wiping the cache sends every following search to GitHub and burns the shared rate limit, so it is an operator action.
- **Favorites store a snapshot:** stars, forks and language are saved with the favorite, so the list renders without one GitHub call per item. The trade-off is that the numbers can get stale.

## Known limitations

- Concurrent identical cache misses each call GitHub (no request coalescing or locking).
- GitHub's user search returns only `login`, `avatar_url` and `html_url`, not `name` or `location`. Fetching those needs a `GET /users/{login}` per result, which was left out to stay within rate limits.
- SQLite is fine for a single instance. Running several API replicas would need PostgreSQL.
- The client stores JWTs in `localStorage`. For a production app, httpOnly cookies would be safer against XSS.
- `manage.py check --deploy` warnings about HSTS and secure cookies assume TLS termination in front of the app, which this setup doesn't include.

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker run -d -p 6379:6379 redis:7-alpine     # optional: without it, search runs uncached

export DJANGO_DEBUG=true                      # allows the built-in dev SECRET_KEY
python manage.py migrate
python manage.py runserver

cd frontend && npm ci && npm run dev          # http://localhost:5173
```

Checks (the same ones CI runs):

```bash
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
coverage run manage.py test && coverage report   # Redis tests are skipped when no Redis is reachable
```

### Configuration

| Variable | Default | |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Required unless `DJANGO_DEBUG=true` |
| `DJANGO_DEBUG` | `false` | |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | Comma-separated |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `SEARCH_CACHE_TTL` | `7200` | Seconds |
| `GITHUB_TOKEN` | empty | Optional; raises the search rate limit |
| `GITHUB_TIMEOUT` | `10` | Seconds |
| `SQLITE_PATH` | `./db.sqlite3` | `/data/db.sqlite3` in Docker (a named volume) |

## Project layout

```
config/       settings, URLs, WSGI
search/       GitHub client, caching service, search and clear-cache views
favorites/    registration, JWT auth wiring, favorites model and API
frontend/     React + Vite client (built and served by nginx in Docker)
```
