"""Runs against a real Redis (provided in CI); skipped when none is reachable."""

import unittest

import redis
from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase

from search.cache import build_key, clear_search_cache


def redis_available() -> bool:
    try:
        return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1).ping()
    except redis.RedisError:
        return False


@unittest.skipUnless(redis_available(), "Redis is not reachable")
class RedisCacheTests(SimpleTestCase):
    # Only touches its own keys, so running it against a dev Redis is safe.
    def setUp(self):
        self.raw = redis.Redis.from_url(settings.REDIS_URL)
        clear_search_cache()
        self.addCleanup(clear_search_cache)
        self.addCleanup(cache.delete, "test:unrelated")
        self.addCleanup(self.raw.delete, "test-other-app:key")

    def test_clear_only_removes_search_keys(self):
        cache.set(build_key("users", "john", 1, 30), {"items": []})
        cache.set(build_key("repositories", "django", 1, 30), {"items": []})
        cache.set("test:unrelated", "keep me")
        self.raw.set("test-other-app:key", "keep me too")

        self.assertEqual(clear_search_cache(), 2)
        self.assertEqual(cache.get("test:unrelated"), "keep me")
        self.assertEqual(self.raw.get("test-other-app:key"), b"keep me too")

    def test_ttl_is_set_on_search_entries(self):
        key = build_key("users", "john", 1, 30)
        cache.set(key, {"items": []}, settings.SEARCH_CACHE_TTL)
        self.assertGreater(cache.ttl(key), 0)
