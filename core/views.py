
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from .models import Premio, Evento, Centro, UsuarioDjango, PerfilFirebase, Canje, Sugerencia
import uuid
from django.http import JsonResponse, HttpResponseForbidden
from .supabase_client import SupabaseClient
from django.contrib.admin.views.decorators import staff_member_required

def home(request):
    return render(request, 'index.html')


def login_screen(request):
    """Pantalla estática que muestra el botón de iniciar sesión con Google y las APIs disponibles."""
    from django.contrib.auth import authenticate, login, get_user_model

    error = None
    # Si es POST, intentar autenticar localmente y mantener errores en la misma pantalla
    if request.method == 'POST':
        login_val = request.POST.get('login', '').strip()
        password = request.POST.get('password', '')

        username_for_auth = login_val
        # si el usuario introdujo un correo, buscar el username asociado
        if '@' in login_val:
            try:
                User = get_user_model()
                u = User.objects.filter(email__iexact=login_val).first()
                if u:
                    username_for_auth = u.get_username()
            except Exception:
                username_for_auth = login_val

            user = authenticate(request, username=username_for_auth, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')
            else:
                # Intentar autenticar contra Supabase (app users)
                try:
                    supa = SupabaseClient()
                    resp = supa.sign_in(login_val, password)
                    # debug: registrar intento de login y respuesta de Supabase
                    try:
                        with open('login_debug.log', 'a', encoding='utf-8') as f:
                            import datetime, json
                            f.write(f"[{datetime.datetime.utcnow().isoformat()}] LOGIN ATTEMPT: {login_val}\n")
                            f.write(f"  local_auth_username: {username_for_auth}\n")
                            f.write(f"  supabase_error: {getattr(resp, 'error', None)}\n")
                            try:
                                # dump entire resp.data for inspection
                                f.write("  supabase_data: \n")
                                f.write(json.dumps(resp.data, ensure_ascii=False, indent=2))
                                f.write("\n")
                            except Exception:
                                f.write(f"  supabase_data (repr): {repr(resp.data)}\n")
                            f.write("\n")
                    except Exception:
                        pass
                    if resp and getattr(resp, 'data', None) and not getattr(resp, 'error', None):
                        # Resp.data typically contains access_token and user
                        udata = resp.data.get('user') if isinstance(resp.data, dict) else None
                        email = None
                        if isinstance(udata, dict):
                            email = udata.get('email')
                        # fallback: use login_val if looks like email
                        if not email and '@' in login_val:
                            email = login_val

                        if email:
                            UserModel = get_user_model()
                            user_obj, created = UserModel.objects.get_or_create(username=email, defaults={'email': email})
                            if created:
                                user_obj.set_unusable_password()
                                user_obj.save()
                            # ensure Django knows which backend we're using when logging in
                            login(request, user_obj, backend='django.contrib.auth.backends.ModelBackend')
                            return redirect('/')
                        else:
                            error = 'El usuario y/o la contraseña son incorrectos.'
                except Exception as e:
                    print('Error autenticando en Supabase:', e)
                    error = 'Error al autenticar. Intente de nuevo.'

    return render(request, 'login_screen.html', {'error': error})


def mapa(request):
    # La plantilla se encarga de pedir los centros via AJAX (/api/centros/),
    # por lo que no es necesario consultar la base de datos local.
    # Esto evita errores cuando DATABASE_URL no está configurado.
    return render(request, 'mapa.html')


def catalogo(request):
    """Catálogo obtiene las recompensas disponibles directamente de Supabase.
    No usamos el modelo local porque la base de datos puede estar vacía.
    """
    supa = SupabaseClient()
    premios = []
    try:
        resp = (
            supa.client.table('recompensas')
            .select('*')
            .eq('disponible', True)
            .order('puntos_requeridos', desc=False)
            .execute()
        )
        premios = resp.data if resp and getattr(resp, 'data', None) else []
    except Exception as e:
        print('Error consultando recompensas en Supabase:', e)
        premios = []
    return render(request, 'catalogo.html', {'premios': premios})


def eventos(request):
    """Obtiene eventos desde Supabase."""
    supa = SupabaseClient()
    eventos = []
    try:
        resp = (
            supa.client.table('eventos')
            .select('*')
            .order('fecha_evento', desc=True)
            .execute()
        )
        eventos = resp.data if resp and getattr(resp, 'data', None) else []
    except Exception as e:
        print('Error consultando eventos en Supabase:', e)
        eventos = []
    return render(request, 'eventos.html', {'eventos': eventos})


# ─────────────────────────────────────────────
# PERFIL DE USUARIO
# ─────────────────────────────────────────────

@login_required
def perfil(request):
    usuario = request.user
    supa = SupabaseClient()
    # obtener perfil de Supabase (preferir su imagen)
    perfil_firebase = None
    try:
        resp = supa.client.table('perfiles').select('*').eq('correo', usuario.email).execute()
        perfil_firebase = resp.data[0] if resp and resp.data else None
        # debug: show raw Supabase profile row
        print('DEBUG perfil_firebase:', perfil_firebase)
    except Exception as e:
        print('Error consultando perfil en Supabase:', e)

    # intentar obtener URL de avatar: preferir imagen del perfil en Supabase,
    # si no existe, usar la imagen de la cuenta social (Google) como fallback
    avatar_url = None
    if perfil_firebase:
        avatar_url = perfil_firebase.get('imagen_url') or perfil_firebase.get('imagen') or None
    if not avatar_url:
        try:
            sa = usuario.socialaccount_set.first()
            if sa and isinstance(sa.extra_data, dict):
                avatar_url = sa.extra_data.get('picture')
        except Exception:
            avatar_url = None

    # ajustar objetos para la plantilla
    ultimos_canjes = []
    total_canjes = 0
    saldo_puntos = 0
    if perfil_firebase:
        try:
            # saldo de puntos
            saldo_puntos = perfil_firebase.get('eco_puntos_saldo', 0)
            # últimos canjes
            canjes_resp = (
                supa.client.table('canjes')
                .select('*')
                .eq('id_usuario', perfil_firebase.get('id'))
                .order('fecha_canje', desc=True)
                .limit(3)
                .execute()
            )
            raw = canjes_resp.data or []
            total_resp = (
                supa.client.table('canjes')
                .select('id', count='estimated')
                .eq('id_usuario', perfil_firebase.get('id'))
                .execute()
            )
            total_canjes = len(raw) if total_resp is None else (total_resp.data and len(total_resp.data) or 0)

            # transformar cada canje a la estructura que espera la plantilla
            for c in raw:
                premio = {
                    'title': c.get('tipo_recompensa'),
                    'points_cost': c.get('monto_puntos_restados'),
                }
                ultimos_canjes.append({
                    'premio': premio,
                    # la plantilla espera campos quantity, created_at, fulfilled
                    'quantity': 1,
                    'created_at': c.get('fecha_canje') or c.get('created_at'),
                    'fulfilled': c.get('estado') == 'exitoso',
                })
        except Exception as e:
            print('Error obteniendo canjes en perfil:', e)
            ultimos_canjes = []
            total_canjes = 0

    # añadir puntos al objeto usuario para que la plantilla los muestre
    try:
        usuario.points = saldo_puntos
    except Exception:
        pass

    return render(request, 'perfil_usuario.html', {
        'usuario': usuario,
        'perfil_firebase': perfil_firebase,
        'ultimos_canjes': ultimos_canjes,
        'total_canjes': total_canjes,
        'qr_url': None,
        'avatar_url': avatar_url,
    })


@login_required
def api_perfil(request):
    """Endpoint JSON: devuelve el perfil del usuario autenticado desde Supabase."""
    usuario = request.user
    supa = SupabaseClient()
    try:
        resp = supa.client.table('perfiles').select('*').eq('correo', usuario.email).execute()
        perfil = resp.data[0] if resp.data else None
        return JsonResponse({'perfil': perfil}, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_editar_perfil(request):
    """Permite actualizar campos del perfil en Supabase (solo si existe)."""
    if request.method != 'POST':
        return HttpResponseForbidden()

    usuario = request.user
    supa = SupabaseClient()
    try:
        resp = supa.client.table('perfiles').select('*').eq('correo', usuario.email).execute()
        perfil = resp.data[0] if resp.data else None
        if not perfil:
            return JsonResponse({'error': 'Perfil no encontrado en Supabase'}, status=404)

        data = {}
        nombre = request.POST.get('first_name')
        apellido = request.POST.get('last_name')
        telefono = request.POST.get('telefono')
        if nombre is not None:
            data['nombre'] = nombre
        if apellido is not None:
            data['apellido'] = apellido
        if telefono is not None:
            data['telefono'] = telefono

        if not data:
            return JsonResponse({'error': 'No hay datos para actualizar'}, status=400)

        upd = supa.client.table('perfiles').update(data).eq('id', perfil.get('id')).execute()
        return JsonResponse({'perfil': upd.data[0] if upd.data else None})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@staff_member_required
def admin_centros(request):
    """Panel sencillo para administradores: listar centros pendientes desde Supabase."""
    supa = SupabaseClient()
    try:
        # Obtener centros pendientes (no validados)
        resp = (
            supa.client.table('centros_acopio')
            .select('*')
            .eq('validado', False)
            .order('created_at', desc=False)
            .execute()
        )
    except Exception as e:
        print('Error listando centros en Supabase:', e)
        resp = None

    centros = resp.data if resp and getattr(resp, 'data', None) else []
    return render(request, 'admin_centros.html', {'centros': centros})


@staff_member_required
def admin_centros_accion(request):
    """Recibe POST con 'centro_id' y 'accion' ('aprobar'|'rechazar') y actualiza Supabase."""
    if request.method != 'POST':
        return HttpResponseForbidden()

    centro_id = request.POST.get('centro_id')
    accion = request.POST.get('accion')
    if not centro_id or accion not in ('aprobar', 'rechazar'):
        return redirect('admin_centros')

    supa = SupabaseClient()
    try:
        if accion == 'aprobar':
            update = {'validado': True, 'estado_operativo': True}
        else:
            update = {'validado': False, 'estado_operativo': False}

        supa.client.table('centros_acopio').update(update).eq('id', int(centro_id)).execute()
    except Exception as e:
        print('Error actualizando centro en Supabase:', e)

    return redirect('admin_centros')


def api_centros(request):
    """Endpoint público que devuelve centros aprobados/validados desde Supabase en JSON."""
    supa = SupabaseClient()
    try:
        # No filtrar por 'validado' aquí: muchos centros en Supabase aún no están validados.
        # Devolvemos todos y la plantilla/JS decide cómo mostrarlos.
        resp = supa.client.table('centros_acopio').select('*').execute()
        centros = resp.data if resp and getattr(resp, 'data', None) else []
        # Filtrar centros que tengan coordenadas
        resultados = []
        for c in centros:
            lat = c.get('latitud') or c.get('latitude')
            lng = c.get('longitud') or c.get('longitude')
            if lat is None or lng is None:
                continue
            resultados.append({
                'id': c.get('id'),
                'nombre': c.get('nombre_comercial') or c.get('name'),
                'direccion': c.get('direccion_texto') or c.get('address'),
                'lat': float(lat),
                'lng': float(lng),
                'validado': bool(c.get('validado')),
                'correo': c.get('correo_contacto') or c.get('contact_email'),
                'telefono': c.get('telefono_contacto') or c.get('contact_phone'),
                'foto': c.get('url_foto_portada') or c.get('url_foto') or c.get('foto')
            })
        return JsonResponse({'centros': resultados})
    except Exception as e:
        print('Error en api_centros:', e)
        return JsonResponse({'error': str(e)}, status=500)


def api_recompensas(request):
    """Endpoint público que retorna recompensas disponibles en JSON."""
    supa = SupabaseClient()
    premios = []
    
    try:
        resp = (
            supa.client.table('recompensas')
            .select('*')
            .eq('disponible', True)
            .order('puntos_requeridos', desc=False)
            .execute()
        )
        premios = resp.data if resp and getattr(resp, 'data', None) else []
    except Exception as e:
        print('Error obteniendo recompensas de Supabase:', e)
        premios = []
    
    # Si no hay datos en Supabase, devolver datos de ejemplo para testing
    if not premios:
        premios = [
            {'id': 1, 'nombre': 'Recarga Telcel $20', 'descripcion': 'Recarga rápida', 'puntos_requeridos': 900, 'imagen_url': None, 'disponible': True},
            {'id': 2, 'nombre': 'Recarga Telcel $50', 'descripcion': 'Recarga intermedia', 'puntos_requeridos': 2000, 'imagen_url': None, 'disponible': True},
            {'id': 3, 'nombre': 'Recarga Telcel $100', 'descripcion': 'Recarga premium', 'puntos_requeridos': 3800, 'imagen_url': None, 'disponible': True},
            # Variantes de Bait: mismos tramos/precios que las recargas Telcel
            {'id': 10, 'nombre': 'Bait - Kit $20', 'descripcion': 'Kit bait pequeño', 'puntos_requeridos': 900, 'imagen_url': None, 'disponible': True},
            {'id': 11, 'nombre': 'Bait - Kit $50', 'descripcion': 'Kit bait mediano', 'puntos_requeridos': 2000, 'imagen_url': None, 'disponible': True},
            {'id': 12, 'nombre': 'Bait - Kit $100', 'descripcion': 'Kit bait grande', 'puntos_requeridos': 3800, 'imagen_url': None, 'disponible': True},
        ]
    
    # Normalizar key de puntos: algunas filas pueden venir con 'puntos' o 'puntos_requeridos'
    for p in premios:
        if p.get('puntos_requeridos') is None and p.get('puntos') is not None:
            try:
                p['puntos_requeridos'] = int(p.get('puntos'))
            except Exception:
                p['puntos_requeridos'] = 0

    # Si no hay imagen, intentar mapear a archivos locales del proyecto Flutter
    import os
    from django.conf import settings
    flutter_static_dir = None
    # Buscar en STATICFILES_DIRS por una carpeta que contenga 'ecoloop_flutter' o coincida con nombre conocido
    for d in getattr(settings, 'STATICFILES_DIRS', []):
        try:
            dd = str(d)
            if 'ecoloop_flutter' in dd or dd.endswith('assets\\images') or dd.endswith('assets/images'):
                flutter_static_dir = dd
                break
        except Exception:
            continue

    # mapeo básico de nombres a archivos conocidos
    mapping = {
        'telcel': 'telcel.png',
        'recarga': 'telcel.png',
        'bait': 'bait.png',
        'default': 'logo.png',
    }

    for p in premios:
        if not p.get('imagen_url'):
            nombre = (p.get('nombre') or '').lower()
            chosen = None
            for k, fn in mapping.items():
                if k in nombre:
                    chosen = fn
                    break
            if not chosen:
                chosen = mapping['default']

            # if flutter_static_dir exists and file present, set imagen_url to the static URL
            if flutter_static_dir and os.path.exists(os.path.join(flutter_static_dir, chosen)):
                p['imagen_url'] = settings.STATIC_URL + chosen
            else:
                # fallback to generic static path (assume STATICFILES_DIRS has logo.png)
                p['imagen_url'] = settings.STATIC_URL + chosen

    return JsonResponse({'premios': premios})


def api_supacentros_debug(request):
    """Endpoint de diagnóstico: devuelve la respuesta cruda de la consulta Supabase para centros."""
    supa = SupabaseClient()
    try:
        resp = supa.client.table('centros_acopio').select('*').limit(20).execute()
        return JsonResponse({'data': resp.data, 'error': resp.error})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def editar_perfil(request):
    usuario = request.user
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        
        if first_name:
            usuario.first_name = first_name
        if last_name:
            usuario.last_name = last_name
        if telefono:
            usuario.telefono = telefono
        
        usuario.save()
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('perfil')
    
    return render(request, 'editar_perfil.html', {'usuario': usuario})


@login_required
@login_required
def historial_canjes(request):
    """Muestra el historial completo de canjes consultando Supabase."""
    usuario = request.user
    total_puntos_usados = 0
    canjes = []

    perfil_id = None
    try:
        supa = SupabaseClient()
        perfil_resp = (
            supa.client.table('perfiles')
            .select('id')
            .eq('correo', usuario.email)
            .single()
            .execute()
        )
        if perfil_resp and perfil_resp.data:
            perfil_id = perfil_resp.data.get('id')
    except Exception as e:
        print('Error consultando perfil en Supabase para historial:', e)
        perfil_id = None

    if perfil_id:
        try:
            resp = (
                supa.client.table('canjes')
                .select('*')
                .eq('id_usuario', perfil_id)
                .order('fecha_canje', desc=True)
                .execute()
            )
            raw = resp.data or []
            total_puntos_usados = sum(c.get('monto_puntos_restados', 0) for c in raw)
            for c in raw:
                premio = {
                    'title': c.get('tipo_recompensa'),
                    'points_cost': c.get('monto_puntos_restados'),
                }
                canjes.append({
                    'premio': premio,
                    'quantity': 1,
                    'created_at': c.get('fecha_canje') or c.get('created_at'),
                    'fulfilled': c.get('estado') == 'exitoso',
                })
        except Exception as e:
            print('Error obteniendo historial de canjes Supabase:', e)
            canjes = []
            total_puntos_usados = 0

    return render(request, 'historial_canjes.html', {
        'canjes': canjes,
        'total_puntos_usados': total_puntos_usados,
    })


@login_required
def sincronizar_qr(request):
    messages.info(request, 'Tu QR se genera desde la app móvil. Ábrela para verlo.')
    return redirect('perfil')


@login_required
def sugerencias(request):
    """Gestiona sugerencias del usuario, usando Supabase."""
    usuario = request.user
    supa = SupabaseClient()
    
    # obtener id del perfil
    perfil_id = None
    try:
        perfil_resp = (
            supa.client.table('perfiles')
            .select('id')
            .eq('correo', usuario.email)
            .single()
            .execute()
        )
        if perfil_resp and perfil_resp.data:
            perfil_id = perfil_resp.data.get('id')
    except Exception as e:
        print('Error obteniendo perfil para sugerencias:', e)
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo', 'otro')
        mensaje = request.POST.get('mensaje', '').strip()
        if not mensaje:
            messages.error(request, 'El mensaje no puede estar vacío.')
            return render(request, 'sugerencias.html')
        
        if perfil_id:
            try:
                supa.client.table('sugerencias').insert({
                    'id_usuario': perfil_id,
                    'tipo': tipo,
                    'mensaje': mensaje,
                }).execute()
                messages.success(request, '¡Gracias! Tu mensaje fue enviado.')
            except Exception as e:
                print('Error insertando sugerencia:', e)
                messages.error(request, 'No se pudo enviar tu sugerencia.')
        else:
            messages.error(request, 'No se encontró tu perfil de usuario.')
        
        return redirect('perfil')
    
    # obtener sugerencias del usuario
    mis_sugerencias = []
    if perfil_id:
        try:
            resp = (
                supa.client.table('sugerencias')
                .select('*')
                .eq('id_usuario', perfil_id)
                .order('created_at', desc=True)
                .execute()
            )
            mis_sugerencias = resp.data or []
        except Exception as e:
            print('Error obteniendo sugerencias:', e)
    
    return render(request, 'sugerencias.html', {'mis_sugerencias': mis_sugerencias})


# ─────────────────────────────────────────────
# PERFIL DE CENTRO
# ─────────────────────────────────────────────

@login_required
def perfil_centro(request):
    usuario = request.user
    try:
        perfil_firebase = PerfilFirebase.objects.get(correo=usuario.email)
        centro = Centro.objects.get(id_usuario=perfil_firebase)
    except (PerfilFirebase.DoesNotExist, Centro.DoesNotExist):
        centro = None
        perfil_firebase = None
    
    eventos_centro = Evento.objects.filter(creado_por=perfil_firebase).order_by('-fecha_evento') if perfil_firebase else []
    
    return render(request, 'perfil_centro.html', {
        'centro': centro,
        'eventos': eventos_centro,
    })


@login_required
def editar_perfil_centro(request):
    usuario = request.user
    
    try:
        perfil_firebase = PerfilFirebase.objects.get(correo=usuario.email)
        centro = Centro.objects.get(id_usuario=perfil_firebase)
    except (PerfilFirebase.DoesNotExist, Centro.DoesNotExist):
        messages.error(request, 'No tienes un centro registrado.')
        return redirect('perfil_centro')
    
    if request.method == 'POST':
        centro.nombre_comercial = request.POST.get('nombre_centro', centro.nombre_comercial).strip()
        centro.direccion_texto = request.POST.get('direccion', centro.direccion_texto).strip()
        centro.telefono_contacto = request.POST.get('telefono', centro.telefono_contacto).strip()
        
        lat = request.POST.get('latitud', '').strip()
        lng = request.POST.get('longitud', '').strip()
        if lat and lng:
            try:
                centro.latitud = float(lat)
                centro.longitud = float(lng)
            except ValueError:
                messages.error(request, 'Coordenadas inválidas.')
                return render(request, 'editar_perfil_centro.html', {'centro': centro})
        
        centro.save()
        messages.success(request, 'Datos del centro actualizados.')
        return redirect('perfil_centro')
    
    return render(request, 'editar_perfil_centro.html', {'centro': centro})


# ─────────────────────────────────────────────
# FLUJO DE REGISTRO
# ─────────────────────────────────────────────

def completar_registro(request):
    if not request.user.is_authenticated:
        return redirect('/accounts/google/login/')
    
    # Verificar si ya tiene perfil completo
    try:
        PerfilFirebase.objects.get(correo=request.user.email)
        # Ya tiene perfil, redirigir
        return redirect('home')
    except PerfilFirebase.DoesNotExist:
        pass
    
    return render(request, 'elegir_tipo.html')


def completar_usuario(request):
    if not request.user.is_authenticated:
        return redirect('/accounts/google/login/')
    
    # Verificar si ya tiene perfil
    try:
        PerfilFirebase.objects.get(correo=request.user.email)
        messages.warning(request, 'Tu cuenta ya está configurada.')
        return redirect('home')
    except PerfilFirebase.DoesNotExist:
        pass
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        
        # Crear perfil en Firebase (simulado)
        perfil = PerfilFirebase.objects.create(
            id=uuid.uuid4(),
            nombre=first_name,
            apellido=last_name,
            telefono=telefono,
            correo=request.user.email,
            tipo_usuario='comun',
            eco_puntos_saldo=0,
            estado_cuenta=True
        )
        
        messages.success(request, f'¡Bienvenido, {first_name}! Tu cuenta está lista.')
        return redirect('home')
    
    return render(request, 'completar_usuario.html')


def completar_centro(request):
    if not request.user.is_authenticated:
        return redirect('/accounts/google/login/')
    
    # Verificar si ya tiene perfil
    try:
        PerfilFirebase.objects.get(correo=request.user.email)
        messages.warning(request, 'Tu cuenta ya está configurada.')
        return redirect('home')
    except PerfilFirebase.DoesNotExist:
        pass
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        nombre_centro = request.POST.get('nombre_centro', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        
        if not nombre_centro:
            messages.error(request, 'El nombre del centro es obligatorio.')
            return render(request, 'completar_centro.html')
        
        # Crear perfil de centro en Firebase
        perfil = PerfilFirebase.objects.create(
            id=uuid.uuid4(),
            nombre=first_name,
            apellido=last_name,
            telefono=telefono,
            correo=request.user.email,
            tipo_usuario='centro',
            eco_puntos_saldo=0,
            estado_cuenta=True
        )
        
        # Crear centro
        centro = Centro.objects.create(
            nombre_comercial=nombre_centro,
            direccion_texto=direccion,
            telefono_contacto=telefono,
            correo_contacto=request.user.email,
            estado_operativo=False,
            validado=False,
            id_usuario=perfil
        )
        
        messages.success(request, 'Solicitud enviada. Un administrador la revisará pronto.')
        return render(request, 'centro_pendiente.html', {'centro': centro})
    
    return render(request, 'completar_centro.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('home')