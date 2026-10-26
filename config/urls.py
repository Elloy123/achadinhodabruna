from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Antes de admin.site.urls, senão o catch-all do admin responde 404.
    path("admin/painel/", include("painel.urls")),
    path("admin/", admin.site.urls),
    path("", include("loja.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
