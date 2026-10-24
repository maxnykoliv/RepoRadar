from django.contrib import admin

from .models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "stargazers_count", "created_at")
    list_select_related = ("user",)
    search_fields = ("full_name", "user__username")
