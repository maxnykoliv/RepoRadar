from django.urls import re_path

from .views import ClearCacheView, SearchView

urlpatterns = [
    re_path(r"^search/?$", SearchView.as_view(), name="search"),
    re_path(r"^clear-cache/?$", ClearCacheView.as_view(), name="clear-cache"),
]
