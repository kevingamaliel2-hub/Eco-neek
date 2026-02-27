# Temporal debug endpoints
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .supabase_client import SupabaseClient
import json

@login_required
def debug_perfil(request):
    """Diagnóstico: Ver exactamente qué devuelve Supabase para el perfil."""
    usuario = request.user
    supa = SupabaseClient()
    
    try:
        # Intentar consulta directa
        url = supa._table_url('perfiles')
        params = {'select': '*', 'correo': f'eq.{usuario.email}'}
        
        import requests
        resp = requests.request('GET', url, headers=supa.headers, params=params)
        
        return JsonResponse({
            'usuario_email': usuario.email,
            'status_code': resp.status_code,
            'response_text': resp.text,
            'response_json': resp.json() if resp.headers.get('content-type') == 'application/json' else None,
            'headers_sent': dict(supa.headers),
            'params_sent': params,
            'url': url,
        }, safe=False)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'type': type(e).__name__,
        }, status=500)

@login_required
def debug_centros(request):
    """Diagnóstico: Ver exactamente qué devuelve Supabase para centros."""
    supa = SupabaseClient()
    
    try:
        url = supa._table_url('centros_acopio')
        params = {'select': '*'}
        
        import requests
        resp = requests.request('GET', url, headers=supa.headers, params=params)
        
        return JsonResponse({
            'status_code': resp.status_code,
            'response_text': resp.text[:500],  # primeros 500 chars
            'response_json': resp.json() if resp.headers.get('content-type') == 'application/json' else None,
        }, safe=False)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'type': type(e).__name__,
        }, status=500)
