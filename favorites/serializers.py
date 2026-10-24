from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Favorite

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def validate_email(self, value):
        # Django's User doesn't enforce unique emails at the database level.
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        # Pass a transient user so the similarity check can compare the
        # password against the username and email.
        candidate = User(username=attrs["username"], email=attrs["email"])
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

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
            "stargazers_count",
            "forks_count",
            "language",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
        extra_kwargs = {
            "description": {"allow_null": True},
            "language": {"allow_null": True},
        }

    def validate_repo_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("Repository ID must be positive.")
        return value

    def validate_html_url(self, value):
        if not value.startswith("https://github.com/"):
            raise serializers.ValidationError("Must be a github.com repository URL.")
        return value

    def validate(self, attrs):
        # GitHub sends null for a missing description or language.
        for field in ("description", "language"):
            if attrs.get(field) is None:
                attrs[field] = ""
        return attrs
