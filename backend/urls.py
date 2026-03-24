# backend/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from core import api
from core import views as core_views
import two_factor.urls as two_factor_urls

router = routers.DefaultRouter()
router.register(r'users', api.UserViewSet, basename='user')
router.register(r'centros', api.CentroViewSet, basename='centro')
router.register(r'materiales', api.MaterialViewSet, basename='material')
router.register(r'premios', api.PremioViewSet, basename='premio')
router.register(r'canjes', api.CanjeViewSet, basename='canje')
router.register(r'eventos', api.EventoViewSet, basename='evento')
router.register(r'sugerencias', api.SugerenciaViewSet, basename='sugerencia')

# two_factor.urls reports urlpatterns as (patterns, app_name), but Django's URLResolver
# expects app_name separately. Passing a tuple into include() is the correct way.
# This avoids the SystemCheckError about invalid URL pattern 'two_factor'.
if isinstance(two_factor_urls.urlpatterns, tuple) and len(two_factor_urls.urlpatterns) == 2:
    two_factor_patterns, two_factor_app_name = two_factor_urls.urlpatterns
else:
    two_factor_patterns = two_factor_urls.urlpatterns
    two_factor_app_name = getattr(two_factor_urls, 'app_name', 'two_factor')

urlpatterns = [
    path('admin/', admin.site.urls),
    # Override account login route to use custom logic (and still keep allauth routes).
    path('accounts/login/', core_views.login_screen, name='account_login'),
    path('accounts/social/signup/', core_views.social_signup_redirect),
    path('accounts/3rdparty/signup/', core_views.social_signup_redirect),
    path('accounts/', include('allauth.urls')),
    path('', include((two_factor_patterns, two_factor_app_name), namespace='two_factor')),
    path('api/', include(router.urls)),
    path('api/auth/register/', api.RegisterView.as_view(), name='register'),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

handler404 = 'core.views.custom_404'