from rest_framework import serializers

SEARCH_TYPES = ("users", "repositories", "issues")
GITHUB_MAX_RESULTS = 1000
MAX_QUERY_LENGTH = 256


class SearchRequestSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=SEARCH_TYPES, help_text="Entity to search for.")
    query = serializers.CharField(max_length=MAX_QUERY_LENGTH, help_text="Search text (required).")
    page = serializers.IntegerField(min_value=1, default=1)
    per_page = serializers.IntegerField(min_value=1, max_value=100, default=30)

    def validate(self, attrs):
        if attrs["page"] * attrs["per_page"] > GITHUB_MAX_RESULTS:
            raise serializers.ValidationError(
                f"GitHub only returns the first {GITHUB_MAX_RESULTS} results; reduce page or per_page."
            )
        return attrs


class SearchResponseSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=SEARCH_TYPES)
    query = serializers.CharField()
    page = serializers.IntegerField()
    per_page = serializers.IntegerField()
    cached = serializers.BooleanField(help_text="True when served from Redis without calling GitHub.")
    total_count = serializers.IntegerField()
    incomplete_results = serializers.BooleanField()
    items = serializers.ListField(child=serializers.DictField(), help_text="Raw GitHub result items.")


class ClearCacheResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    deleted = serializers.IntegerField(allow_null=True, help_text="Entries removed, null if the backend can't tell.")


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
