from django.conf import settings
from django.core.cache import cache

from .cache import build_key, normalize_query
from .github_client import github_client


def search(search_type: str, query: str, page: int, per_page: int) -> dict:
    query = normalize_query(query)
    key = build_key(search_type, query, page, per_page)

    payload = cache.get(key)
    cached = payload is not None
    if not cached:
        payload = github_client.search(search_type, query, page, per_page)
        if not payload["incomplete_results"]:
            cache.set(key, payload, settings.SEARCH_CACHE_TTL)

    return {
        "type": search_type,
        "query": query,
        "page": page,
        "per_page": per_page,
        "cached": cached,
        **payload,
    }
