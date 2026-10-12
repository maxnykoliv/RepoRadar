from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APISimpleTestCase

from search.exceptions import GitHubRateLimited, GitHubUnavailable

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PAYLOAD = {"total_count": 1, "incomplete_results": False, "items": [{"login": "john"}]}


@override_settings(CACHES=LOCMEM)
class SearchViewTests(APISimpleTestCase):
    url = "/api/search"

    def setUp(self):
        cache.clear()
        patcher = patch("search.services.github_client.search", return_value=dict(PAYLOAD))
        self.github = patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, **data):
        return self.client.post(self.url, data, format="json")

    def test_query_is_required(self):
        response = self.post(type="users")
        self.assertEqual(response.status_code, 400)
        self.assertIn("query", response.json())

    def test_blank_query_rejected(self):
        self.assertEqual(self.post(type="users", query="   ").status_code, 400)

    def test_too_long_query_rejected(self):
        self.assertEqual(self.post(type="users", query="a" * 257).status_code, 400)

    def test_type_is_required_and_validated(self):
        self.assertEqual(self.post(query="john").status_code, 400)
        self.assertEqual(self.post(type="orgs", query="john").status_code, 400)

    def test_pagination_bounds(self):
        self.assertEqual(self.post(type="users", query="john", page=0).status_code, 400)
        self.assertEqual(self.post(type="users", query="john", per_page=101).status_code, 400)
        self.assertEqual(self.post(type="users", query="john", page=11, per_page=100).status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_trailing_slash_supported(self):
        self.assertEqual(self.client.post("/api/search/", {"type": "users", "query": "john"}, format="json").status_code, 200)

    def test_malformed_json_rejected(self):
        response = self.client.post(self.url, "{bad", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_success_response_shape(self):
        response = self.post(type="users", query="john")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"type": "users", "query": "john", "page": 1, "per_page": 30, "cached": False, **PAYLOAD},
        )
        self.github.assert_called_once_with("users", "john", 1, 30)

    def test_all_three_types_supported(self):
        for search_type in ("users", "repositories", "issues"):
            self.assertEqual(self.post(type=search_type, query="x").status_code, 200)

    def test_second_identical_request_served_from_cache(self):
        self.post(type="users", query="john")
        response = self.post(type="users", query="john")
        self.assertTrue(response.json()["cached"])
        self.assertEqual(self.github.call_count, 1)

    def test_query_normalised_for_cache(self):
        self.post(type="users", query="Foo   Bar")
        response = self.post(type="users", query=" foo bar ")
        self.assertTrue(response.json()["cached"])
        self.assertEqual(self.github.call_count, 1)

    def test_cache_is_separate_per_type_and_page(self):
        self.post(type="users", query="john")
        self.post(type="repositories", query="john")
        self.post(type="users", query="john", page=2)
        self.assertEqual(self.github.call_count, 3)

    @override_settings(SEARCH_CACHE_TTL=7200)
    def test_ttl_is_applied(self):
        with patch("search.services.cache") as fake_cache:
            fake_cache.get.return_value = None
            self.post(type="users", query="john")
        self.assertEqual(fake_cache.set.call_args.args[2], 7200)

    def test_incomplete_results_not_cached(self):
        self.github.return_value = {**PAYLOAD, "incomplete_results": True}
        self.post(type="users", query="john")
        self.post(type="users", query="john")
        self.assertEqual(self.github.call_count, 2)

    def test_rate_limit_returns_429_with_retry_after(self):
        self.github.side_effect = GitHubRateLimited(wait=30)
        response = self.post(type="users", query="john")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "30")

    def test_upstream_errors_are_not_cached(self):
        self.github.side_effect = GitHubUnavailable()
        self.assertEqual(self.post(type="users", query="john").status_code, 502)
        self.github.side_effect = None
        self.github.return_value = dict(PAYLOAD)
        self.assertEqual(self.post(type="users", query="john").status_code, 200)


@override_settings(CACHES=LOCMEM)
class ClearCacheViewTests(APISimpleTestCase):
    def setUp(self):
        cache.clear()
        patcher = patch("search.services.github_client.search", return_value=dict(PAYLOAD))
        self.github = patcher.start()
        self.addCleanup(patcher.stop)

    def _warm_then_clear(self, method):
        self.client.post("/api/search", {"type": "users", "query": "john"}, format="json")
        response = getattr(self.client, method)("/api/clear-cache")
        self.assertEqual(response.status_code, 200)
        again = self.client.post("/api/search", {"type": "users", "query": "john"}, format="json")
        self.assertFalse(again.json()["cached"])
        self.assertEqual(self.github.call_count, 2)

    def test_post_clears_cache(self):
        self._warm_then_clear("post")

    def test_delete_clears_cache(self):
        self._warm_then_clear("delete")

    def test_clearing_empty_cache_is_ok(self):
        self.assertEqual(self.client.post("/api/clear-cache").status_code, 200)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get("/api/clear-cache").status_code, 405)
