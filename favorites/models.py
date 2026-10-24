from django.conf import settings
from django.db import models


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favorites",
    )
    repo_id = models.PositiveBigIntegerField()
    full_name = models.CharField(max_length=255)
    html_url = models.URLField()
    description = models.TextField(blank=True, default="")
    # Snapshot of the repo's stats at the time it was saved, so the favorites
    # list renders without one GitHub API call per item.
    stargazers_count = models.PositiveIntegerField(default=0)
    forks_count = models.PositiveIntegerField(default=0)
    language = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "repo_id"],
                name="unique_user_favorite_repo",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.full_name}"
