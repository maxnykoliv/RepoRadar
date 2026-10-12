# GitHub Search – Backend

Django REST Framework API that proxies the [GitHub Search API](https://docs.github.com/en/rest/search) and caches results in Redis.

## Quick start

```bash
# Option A – Docker
docker compose up --build            # API on http://localhost:8000

# Option B – local
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker run -d -p 6379:6379 redis:7-alpine   # or any local Redis
cp .env.example .env && export $(grep -v '^#' .env | xargs)
python manage.py runserver
```

Swagger UI: `http://localhost:8000/api/docs/` · OpenAPI schema: `/api/schema/`

Tests (no Redis or network needed – cache is in-memory, GitHub is mocked):

```bash
python manage.py test
```

## Endpoints

### `POST /api/search`
```json
{ "type": "repositories", "query": "django rest", "page": 1, "per_page": 30 }
```
`type` ∈ `users | repositories | issues` and `query` are required; `page` (default 1) and `per_page` (default 30, max 100) are optional.

Response `200`:
```json
{ "type": "repositories", "query": "django rest", "page": 1, "per_page": 30,
  "cached": false, "total_count": 123, "incomplete_results": false, "items": [ ... ] }
```
`items` are GitHub's objects, unchanged.

| Status | Meaning |
|---|---|
| 400 | Invalid body (missing/blank/too long query, unknown type, bad pagination) |
| 422 | GitHub rejected the query |
| 429 | GitHub rate limit hit; `Retry-After` header is set |
| 502 / 504 | GitHub unreachable, timed out or returned garbage |

### `POST|DELETE /api/clear-cache`
Removes all cached search results (only this app's keys) → `{"detail": "...", "deleted": <n>}`.

## Design decisions

- **Layers**: `views` (HTTP) → `services` (cache + orchestration) → `github_client` (HTTP to GitHub). Each is testable alone.
- **Cache key** = SHA-256 of `(type, normalised lower-cased query, page, per_page)`. Whitespace/case variants share an entry, since GitHub search is case-insensitive.
- **TTL** is 2 h (`SEARCH_CACHE_TTL`). Errors and `incomplete_results: true` (GitHub's partial results) are never cached.
- **Clear cache** uses `delete_pattern("search:*")`, so unrelated keys in the same Redis survive; `FLUSHDB` would be too destructive.
- **Redis down ⇒ degrade, don't fail**: `IGNORE_EXCEPTIONS` turns cache errors into misses, so search still works (just uncached).
- **Error mapping**: GitHub failures become meaningful statuses (429 + `Retry-After`, 422, 502, 504) instead of a generic 500. A plain 403 isn't mistaken for a rate limit.
- **GitHub's 1000-result cap** is validated up front (`page * per_page ≤ 1000`).
- **No database**: Redis is the only store, so `DATABASES = {}`.
- **Optional `GITHUB_TOKEN`** raises the search limit from 10 to 30 req/min.

## Known limitations

- Concurrent identical cache misses each call GitHub (no request coalescing).
- GitHub's *user search* returns only `login`, `avatar_url`, `html_url`, … – not `name`/`location`. Getting those needs an extra `GET /users/{login}` per result; left out to stay within rate limits.
