from django.db import IntegrityError, transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Favorite
from .serializers import FavoriteSerializer, RegisterSerializer


class AlreadyFavorited(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This repository is already in your favorites."
    default_code = "already_favorited"


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class FavoriteListCreateView(generics.ListCreateAPIView):
    serializer_class = FavoriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Rely on the unique constraint instead of a check-then-insert, which
        # would race when the same repo is starred twice in quick succession.
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user)
        except IntegrityError:
            raise AlreadyFavorited() from None


class FavoriteDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Remove a repository from favorites",
        responses={204: None, 404: OpenApiResponse(description="Not in your favorites")},
    )
    def delete(self, request, repo_id):
        deleted, _ = Favorite.objects.filter(user=request.user, repo_id=repo_id).delete()
        if not deleted:
            return Response({"detail": "Favorite not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)
