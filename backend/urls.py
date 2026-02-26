# backend/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from core import api

router = routers.DefaultRouter()
router.register(r'users', api.UserViewSet, basename='user')
router.register(r'centros', api.CentroViewSet, basename='centro')
router.register(r'materiales', api.MaterialViewSet, basename='material')
router.register(r'premios', api.PremioViewSet, basename='premio')
router.register(r'canjes', api.CanjeViewSet, basename='canje')
router.register(r'eventos', api.EventoViewSet, basename='evento')
router.register(r'sugerencias', api.SugerenciaViewSet, basename='sugerencia')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('api/', include(router.urls)),
    path('api/auth/register/', api.RegisterView.as_view(), name='register'),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])