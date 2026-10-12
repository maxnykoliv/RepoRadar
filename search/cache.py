import hashlib
import json

from django.core.cache import cache

KEY_NAMESPACE = "search"


def normalize_query(query: str) -> str:
    return " ".join(query.split())


def build_key(search_type: str, query: str, page: int, per_page: int) -> str:
    raw = json.dumps([search_type, normalize_query(query).lower(), page, per_page])
    return f"{KEY_NAMESPACE}:{hashlib.sha256(raw.encode()).hexdigest()}"


def clear_search_cache() -> int | None:
    if hasattr(cache, "delete_pattern"):
        return cache.delete_pattern(f"{KEY_NAMESPACE}:*")
    cache.clear()
    return None
