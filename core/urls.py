
from django.urls import path, re_path
from . import views
from django.shortcuts import redirect

def social_signup_redirect(request, *args, **kwargs):
    # Allauth social-signup endpoints use either /accounts/social/signup/ or /accounts/3rdparty/signup/
    # Redirigir a registro personalizado y predeterminar tipo usuario.
    return redirect('/register-screen/?tipo=usuario')

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
    path('proximamente/', views.proximamente, name='proximamente'),
    # Panel de gestión de centros fuera del admin de Django (usa Supabase)
    # La ruta previa "admin/centros/" chocaba con el prefijo de admin de Django,
    # por lo que se movió a una URL independiente.
    path('panel/centros/', views.admin_centros, name='admin_centros'),
    path('panel/centros/accion/', views.admin_centros_accion, name='admin_centros_accion'),
    # Centros API
    # Router already exposes /api/centros/ (Django REST framework). Expose Supabase-backed
    # centros under a separate path to avoid routing conflicts.
    path('api/supacentros/', views.api_centros, name='api_centros_supabase'),
    path('api/recompensas/', views.api_recompensas, name='api_recompensas'),
    path('api/recompensas/', views.api_recompensas, name='api_recompensas'),
    # pantalla de login con botón Google e info de APIs
    path('login-screen/', views.login_screen, name='login_screen'),
    path('register-screen/', views.register_screen, name='register_screen'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    # Override Allauth social signup URLs to always redirect al registro personalizado.
    re_path(r'^accounts/social/signup/$', social_signup_redirect),
    re_path(r'^accounts/3rdparty/signup/$', social_signup_redirect),
    # En core/urls.py, agrega esta línea:
    path('centro/<int:centro_id>/', views.centro_publico, name='centro_publico'),
    # Fallback para rutas no existentes: redirige al home por seguridad.
    # Si empieza con /eventos, redirige a /eventos/ en vez de home.
    re_path(r'^(?P<unmatched>.*)$', views.route_fallback),
]
