from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .cache import clear_search_cache
from .serializers import (
    ClearCacheResponseSerializer,
    ErrorSerializer,
    SearchRequestSerializer,
    SearchResponseSerializer,
)


class SearchView(APIView):
    @extend_schema(
        summary="Search GitHub",
        description=(
            "Searches GitHub for **users**, **repositories** or **issues**. Results are cached in Redis "
            "for 2 hours per (type, query, page, per_page); repeated requests don't hit GitHub."
        ),
        request=SearchRequestSerializer,
        responses={
            200: SearchResponseSerializer,
            400: ErrorSerializer,
            422: ErrorSerializer,
            429: ErrorSerializer,
            502: ErrorSerializer,
            504: ErrorSerializer,
        },
        examples=[
            OpenApiExample("Search repositories", value={"type": "repositories", "query": "django rest", "per_page": 10}, request_only=True),
            OpenApiExample(
                "Response",
                value={
                    "type": "repositories",
                    "query": "django rest",
                    "page": 1,
                    "per_page": 10,
                    "cached": False,
                    "total_count": 1,
                    "incomplete_results": False,
                    "items": [{"id": 1, "full_name": "encode/django-rest-framework", "stargazers_count": 28000}],
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = services.search(data["type"], data["query"], data["page"], data["per_page"])
        return Response(result)


class ClearCacheView(APIView):
    @extend_schema(summary="Clear the search cache", request=None, responses={200: ClearCacheResponseSerializer})
    def post(self, request):
        return self._clear()

    @extend_schema(summary="Clear the search cache", request=None, responses={200: ClearCacheResponseSerializer})
    def delete(self, request):
        return self._clear()

    @staticmethod
    def _clear():
        deleted = clear_search_cache()
        return Response({"detail": "Search cache cleared.", "deleted": deleted})
