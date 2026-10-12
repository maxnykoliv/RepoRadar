from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.urls import path

urlpatterns = [
    path(
        "",
        RedirectView.as_view(pattern_name="swagger-ui", permanent=False)
    ),
    path("api/",
         include("search.urls")
    ),
    path("api/schema/",
         SpectacularAPIView.as_view(),
         name="schema"
    ),
    path("api/docs/",
         SpectacularSwaggerView.as_view(url_name="schema"),
         name="swagger-ui"
    ),
    path("api/", include("favorites.urls")),
]
