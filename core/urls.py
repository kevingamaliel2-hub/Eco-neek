from django.urls import path
from . import views
from . import views_debug

urlpatterns = [
    path('', views.home, name='home'),
    path('mapa/', views.mapa, name='mapa'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('eventos/', views.eventos, name='eventos'),
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    # Supabase-backed API endpoints (no escrituras locales)
    path('api/perfil/', views.api_perfil, name='api_perfil'),
    path('api/perfil/editar/', views.api_editar_perfil, name='api_editar_perfil'),
    path('perfil/canjes/', views.historial_canjes, name='historial_canjes'),
    path('perfil/qr/sincronizar/', views.sincronizar_qr, name='sincronizar_qr'),
    path('sugerencias/', views.sugerencias, name='sugerencias'),
    path('centro/perfil/', views.perfil_centro, name='perfil_centro'),
    path('centro/perfil/editar/', views.editar_perfil_centro, name='editar_perfil_centro'),
    path('completar-registro/', views.completar_registro, name='completar_registro'),
    path('completar-registro/usuario/', views.completar_usuario, name='completar_usuario'),
    path('completar-registro/centro/', views.completar_centro, name='completar_centro'),
    path('logout/', views.logout_view, name='logout'),
    # Admin: gestionar centros (usa Supabase)
    path('admin/centros/', views.admin_centros, name='admin_centros'),
    path('admin/centros/accion/', views.admin_centros_accion, name='admin_centros_accion'),
    # Centros API
    # Router already exposes /api/centros/ (Django REST framework). Expose Supabase-backed
    # centros under a separate path to avoid routing conflicts.
    path('api/supacentros/', views.api_centros, name='api_centros_supabase'),
    path('api/recompensas/', views.api_recompensas, name='api_recompensas'),
    path('api/supacentros_debug/', views.api_supacentros_debug, name='api_supacentros_debug'),
    # Endpoints de diagnóstico temporales
    path('debug/perfil/', views_debug.debug_perfil, name='debug_perfil'),
    path('debug/centros/', views_debug.debug_centros, name='debug_centros'),
    # pantalla de login con botón Google e info de APIs
    path('login-screen/', views.login_screen, name='login_screen'),
]
