
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Favorite

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = [
            "id",
            "repo_id",
            "full_name",
            "html_url",
            "description",
            "created_at",
            "forks_count",
            "stars_count",
            "watchers_count",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_repo_id(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Repository ID must be positive."
            )
        return value
