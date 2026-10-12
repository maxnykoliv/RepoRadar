import json
import time
from unittest.mock import patch

import requests
from django.test import SimpleTestCase

from search.exceptions import GitHubInvalidQuery, GitHubRateLimited, GitHubTimeout, GitHubUnavailable
from search.github_client import GitHubClient


def make_response(status=200, body=None, headers=None, raw=None):
    response = requests.Response()
    response.status_code = status
    response._content = raw if raw is not None else json.dumps(body if body is not None else {}).encode()
    response.headers.update(headers or {})
    return response


class GitHubClientTests(SimpleTestCase):
    def setUp(self):
        self.client = GitHubClient(base_url="https://gh.test", token="", timeout=5)

    def _search(self, response=None, side_effect=None):
        with patch.object(self.client.session, "get", return_value=response, side_effect=side_effect) as get:
            try:
                return self.client.search("users", "john", 2, 10), get
            except Exception as exc:
                return exc, get

    def test_success_returns_trimmed_payload_and_sends_params(self):
        body = {"total_count": 1, "incomplete_results": False, "items": [{"login": "john"}], "extra": "x"}
        result, get = self._search(make_response(body=body))
        self.assertEqual(result, {"total_count": 1, "incomplete_results": False, "items": [{"login": "john"}]})
        args, kwargs = get.call_args
        self.assertEqual(args[0], "https://gh.test/search/users")
        self.assertEqual(kwargs["params"], {"q": "john", "page": 2, "per_page": 10})
        self.assertEqual(kwargs["timeout"], 5)
        self.assertNotIn("Authorization", kwargs["headers"])

    def test_token_is_sent_when_configured(self):
        client = GitHubClient(base_url="https://gh.test", token="abc", timeout=5)
        with patch.object(client.session, "get", return_value=make_response(body={})) as get:
            client.search("issues", "bug")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer abc")

    def test_rate_limit_uses_retry_after_header(self):
        result, _ = self._search(make_response(403, {"message": "x"}, {"Retry-After": "42"}))
        self.assertIsInstance(result, GitHubRateLimited)
        self.assertEqual(result.wait, 42)

    def test_rate_limit_uses_reset_header(self):
        headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(int(time.time()) + 30)}
        result, _ = self._search(make_response(403, {"message": "x"}, headers))
        self.assertIsInstance(result, GitHubRateLimited)
        self.assertTrue(1 <= result.wait <= 30)

    def test_429_is_rate_limited(self):
        result, _ = self._search(make_response(429, {}))
        self.assertIsInstance(result, GitHubRateLimited)

    def test_plain_403_is_not_rate_limit(self):
        result, _ = self._search(make_response(403, {"message": "Forbidden"}))
        self.assertIsInstance(result, GitHubUnavailable)

    def test_422_maps_to_invalid_query_with_github_message(self):
        result, _ = self._search(make_response(422, {"message": "Validation Failed"}))
        self.assertIsInstance(result, GitHubInvalidQuery)
        self.assertEqual(str(result.detail), "Validation Failed")

    def test_server_error_maps_to_unavailable(self):
        result, _ = self._search(make_response(500, {}))
        self.assertIsInstance(result, GitHubUnavailable)

    def test_invalid_json_maps_to_unavailable(self):
        result, _ = self._search(make_response(200, raw=b"<html>"))
        self.assertIsInstance(result, GitHubUnavailable)

    def test_timeout_maps_to_gateway_timeout(self):
        result, _ = self._search(side_effect=requests.Timeout())
        self.assertIsInstance(result, GitHubTimeout)

    def test_connection_error_maps_to_unavailable(self):
        result, _ = self._search(side_effect=requests.ConnectionError())
        self.assertIsInstance(result, GitHubUnavailable)
