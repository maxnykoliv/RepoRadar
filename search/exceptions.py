from rest_framework import status
from rest_framework.exceptions import APIException


class GitHubRateLimited(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "GitHub rate limit exceeded. Please retry later."
    default_code = "github_rate_limited"

    def __init__(self, wait: int | None = None, detail=None):
        super().__init__(detail)
        self.wait = wait


class GitHubInvalidQuery(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "GitHub rejected the search query."
    default_code = "github_invalid_query"


class GitHubUnavailable(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "GitHub returned an unexpected response."
    default_code = "github_unavailable"


class GitHubTimeout(APIException):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    default_detail = "GitHub did not respond in time."
    default_code = "github_timeout"
