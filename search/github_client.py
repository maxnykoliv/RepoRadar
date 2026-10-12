import time

import requests
from django.conf import settings

from .exceptions import (
    GitHubInvalidQuery,
    GitHubRateLimited,
    GitHubTimeout,
    GitHubUnavailable,
)

SEARCH_PATHS = {
    "users": "/search/users",
    "repositories": "/search/repositories",
    "issues": "/search/issues",
}


class GitHubClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or settings.GITHUB_API_URL).rstrip("/")
        self.token = settings.GITHUB_TOKEN if token is None else token
        self.timeout = timeout or settings.GITHUB_TIMEOUT
        self.session = requests.Session()

    def search(self, search_type: str, query: str, page: int = 1, per_page: int = 30) -> dict:
        url = f"{self.base_url}{SEARCH_PATHS[search_type]}"
        try:
            response = self.session.get(
                url,
                params={"q": query, "page": page, "per_page": per_page},
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise GitHubTimeout() from exc
        except requests.RequestException as exc:
            raise GitHubUnavailable("Could not reach GitHub.") from exc

        return self._parse(response)

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _parse(self, response: requests.Response) -> dict:
        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError as exc:
                raise GitHubUnavailable("GitHub returned invalid JSON.") from exc
            return {
                "total_count": body.get("total_count", 0),
                "incomplete_results": body.get("incomplete_results", False),
                "items": body.get("items", []),
            }

        if self._is_rate_limited(response):
            raise GitHubRateLimited(wait=self._retry_after(response))
        if response.status_code == 422:
            raise GitHubInvalidQuery(self._message(response) or None)
        raise GitHubUnavailable(f"GitHub responded with status {response.status_code}.")

    @staticmethod
    def _is_rate_limited(response: requests.Response) -> bool:
        if response.status_code == 429:
            return True
        return response.status_code == 403 and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or "Retry-After" in response.headers
            or "rate limit" in GitHubClient._message(response).lower()
        )

    @staticmethod
    def _retry_after(response: requests.Response) -> int:
        headers = response.headers
        try:
            if "Retry-After" in headers:
                return max(int(headers["Retry-After"]), 1)
            if "X-RateLimit-Reset" in headers:
                return max(int(headers["X-RateLimit-Reset"]) - int(time.time()), 1)
        except ValueError:
            pass
        return 60

    @staticmethod
    def _message(response: requests.Response) -> str:
        try:
            return str(response.json().get("message", ""))
        except (ValueError, AttributeError):
            return ""


github_client = GitHubClient()
