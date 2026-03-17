import requests
import datetime
from urllib.parse import quote_plus
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from .models import Premio, Evento, Centro, UsuarioDjango, PerfilFirebase, Canje, Sugerencia
import uuid
from django.http import JsonResponse, HttpResponseForbidden
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .supabase_client import SupabaseClient
from django.contrib.admin.views.decorators import staff_member_required

# ============================================
# FUNCIÓN DE GEOCODING (DEFINIDA UNA SOLA VEZ)
# ============================================
def obtener_direccion_desde_coordenadas(lat, lng):
    """
    Obtiene la dirección a partir de latitud y longitud usando Nominatim (OSM)
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=18&addressdetails=1"
        headers = {'User-Agent': 'EcoNeek/1.0'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if 'display_name' in data:
                return data['display_name']
    except Exception:
        pass
    return None


def obtener_coordenadas_desde_direccion(direccion):
    """Obtiene lat/lng de una dirección usando Nominatim."""
    if not direccion:
        return None
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=1&q={quote_plus(direccion)}"
        headers = {'User-Agent': 'EcoNeek/1.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                lat = first.get('lat')
                lon = first.get('lon')
                if lat and lon:
                    return {'lat': float(lat), 'lon': float(lon)}
    except Exception:
        pass
    return None


def is_valid_email(email):
    """Validar correo con Django para evitar inyecciones y entradas malformadas."""
    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def proximamente(request):
    return render(request, 'proximamente.html')


def home(request):
    return render(request, 'index.html')


def route_fallback(request, unmatched=None):
    # URL no existente: redirige a home por seguridad.
    # Si es bajo eventos, queda en eventos.
    if request.path.startswith('/eventos'):
        return redirect('/eventos/')
    return redirect('/')


def custom_404(request, exception=None):
    if request.path.startswith('/eventos'):
        return redirect('/eventos/')
    return redirect('/')


def social_signup_redirect(request, *args, **kwargs):
    # Redirigir a registro personalizado con tipo usuario para cuentas Google nuevas.
    return redirect('/register-screen/?tipo=usuario')


def login_screen(request):
    """Formulario de inicio de sesión por correo/contraseña con soporte Google.

    Se limita el número de intentos fallidos en sesión para mitigar ataques de
    fuerza bruta, y los administradores son redirigidos automáticamente al
    panel de centros.
    """
    from django.contrib.auth import authenticate, login, get_user_model

    error = None
    # límite de intentos: almacenamos contador en sesión
    attempts = request.session.get('login_attempts', 0)
    
    if request.method == 'POST':
        if attempts >= 5:
            error = 'Has superado el número máximo de intentos. Espera unos minutos.'
        else:
            login_val = request.POST.get('login', '').strip()
            password = request.POST.get('password', '')

            username_for_auth = login_val
            # si el usuario introdujo un correo, validar y buscar el username asociado
            if '@' in login_val:
                if not is_valid_email(login_val):
                    error = 'Correo electrónico no válido.'
                else:
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
                        request.session['login_attempts'] = 0
                        # si es staff, al panel
                        if user.is_staff:
                            return redirect('admin_centros')
                        return redirect('/')
                    else:
                        # Intentar autenticar contra Supabase (app users)
                        try:
                            supa = SupabaseClient()
                            resp = supa.sign_in(login_val, password)
                            if resp and getattr(resp, 'data', None) and not getattr(resp, 'error', None):
                                # Resp.data typically contains access_token and user
                                udata = resp.data.get('user') if isinstance(resp.data, dict) else None
                                email = None
                                if isinstance(udata, dict):
                                    email = udata.get('email')
                                # fallback: use login_val if looks like email
                                if not email and '@' in login_val:
                                    email = login_val

                                tipo_usuario = 'usuario'  # Valor por defecto
                                if email:
                                    # OBTENER EL PERFIL COMPLETO DE SUPABASE
                                    try:
                                        supa_url = getattr(supa, 'url', None)
                                        supa_key = getattr(supa, 'key', None)
                                        if supa_url and supa_key:
                                            perfil_url = f"{supa_url}/rest/v1/perfiles?correo=eq.{quote_plus(email)}"
                                            perfil_headers = {
                                                'apikey': supa_key,
                                                'Authorization': f'Bearer {supa_key}'
                                            }
                                            perfil_resp = requests.get(perfil_url, headers=perfil_headers)
                                            if perfil_resp.status_code == 200:
                                                perfil_data = perfil_resp.json()
                                                if perfil_data and len(perfil_data) > 0:
                                                    tipo_usuario = perfil_data[0].get('tipo_usuario', 'usuario')
                                    except Exception:
                                        tipo_usuario = 'usuario'

                                    UserModel = get_user_model()
                                    user_obj = UserModel.objects.filter(email__iexact=email).first()
                                    if not user_obj:
                                        user_obj = UserModel.objects.create_user(username=email, email=email)
                                        user_obj.set_unusable_password()

                                    # Si Supabase considera este usuario admin, marcamos is_staff.
                                    # Esto permite acceder al panel admin con @staff_member_required.
                                    if tipo_usuario in ('admin', 'superadmin', 'staff'):
                                        user_obj.is_staff = True
                                    user_obj.save()
                                    login(request, user_obj, backend='django.contrib.auth.backends.ModelBackend')
                                    request.session['login_attempts'] = 0
                                    # GUARDAR EL TIPO DE USUARIO EN LA SESIÓN DE DJANGO
                                    request.session['user_type'] = tipo_usuario
                                    request.session['user_id_supabase'] = udata.get('id') if udata else None
                                    # REDIRIGIR SEGÚN EL TIPO
                                    if user_obj.is_staff:
                                        return redirect('admin_centros')
                                    if tipo_usuario == 'centro':
                                        return redirect('perfil_centro')
                                    return redirect('perfil')
                                else:
                                    error = 'El usuario y/o la contraseña son incorrectos.'
                        except Exception as e:
                            error = 'Error al autenticar. Intente de nuevo.'
            else:
                # Username-based login fallback (sin @)
                try:
                    user = authenticate(request, username=username_for_auth, password=password)
                    if user is not None:
                        login(request, user)
                        request.session['login_attempts'] = 0
                        if user.is_staff:
                            return redirect('admin_centros')
                        return redirect('/')
                    else:
                        error = 'Usuario y/o contraseña incorrectos.'
                except Exception:
                    error = 'Usuario y/o contraseña incorrectos.'

            # incrementar contador cuando falla la autenticación local/Supabase
            if not error:
                attempts += 1
                request.session['login_attempts'] = attempts

    return render(request, 'login_screen.html', {'error': error})


def forgot_password(request):
    error = None
    message = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        if not email:
            error = 'Ingresa un correo electrónico.'
        elif not is_valid_email(email):
            error = 'Correo electrónico no válido.'
        else:
            try:
                supa = SupabaseClient()
                recovery_url = f"{supa.url}/auth/v1/recover"
                headers = {
                    'apikey': supa.key,
                    'Authorization': f'Bearer {supa.key}',
                    'Content-Type': 'application/json',
                }
                payload = {'email': email}
                response = requests.post(recovery_url, json=payload, headers=headers, timeout=20)
                if response.status_code in (200, 204):
                    message = 'Te enviamos un correo para restablecer tu contraseña. Revisa tu bandeja y carpeta de spam.'
                else:
                    message = 'Si el correo existe en nuestro sistema, recibirás un enlace para restablecer la contraseña.'
            except Exception:
                error = 'No se pudo procesar la solicitud. Intenta de nuevo más tarde.'
    return render(request, 'forgot_password.html', {'error': error, 'message': message})


def register_screen(request):
    """Formulario unificado de registro para usuario y centro.
    
    Adapta los campos mostrados según el tipo (usuario o centro) vía query param ?tipo=centro
    Al crear la cuenta, autentica al usuario y lo envía a completar su perfil.
    """
    from django.contrib.auth import login, get_user_model
    from core.models import Centro
    error = None
    success = False

    tipo = request.POST.get('tipo', request.GET.get('tipo', 'usuario'))  # Default 'usuario' si no especifica
    
    # Pre-fill fields en caso de error
    form_data = {
        'nombre': '', 'apellido': '', 'responsable': '', 'nombre_centro': '',
        'telefono': '', 'direccion': '', 'municipio': '', 'horarios': '',
        'codigo_postal': '', 'estado': '', 'localidad': '', 'colonia': '',
        'descripcion_publica': '', 'correo_publico': '',
        'email': '', 'tipo': tipo,
        'dias': [],
        'materiales_seleccionados': []
    }

    supa = SupabaseClient()
    materiales = []
    try:
        materiales = supa.obtener_materiales()
    except Exception:
        materiales = []
    if not materiales:
        materiales = [
            {'id': '1', 'nombre': 'Vidrio'},
            {'id': '2', 'nombre': 'Textiles'},
            {'id': '3', 'nombre': 'TetraPak'},
            {'id': '4', 'nombre': 'Plástico'},
            {'id': '5', 'nombre': 'Papel y cartón'}
        ]
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        terms = request.POST.get('terms')
        
        materiales_seleccionados = request.POST.getlist('materiales')
        dias_semana = []
        for i, nombre_dia in enumerate(['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'], start=1):
            dias_semana.append({
                'nombre': nombre_dia,
                'activo': bool(request.POST.get(f'activo_{i}', 'on')),
                'apertura': request.POST.get(f'apertura_{i}', '08:00'),
                'cierre': request.POST.get(f'cierre_{i}', '18:00')
            })

        form_data.update({
            'nombre': request.POST.get('nombre', '').strip(),
            'apellido': request.POST.get('apellido', '').strip(),
            'responsable': request.POST.get('responsable', '').strip(),
            'nombre_centro': request.POST.get('nombre_centro', '').strip(),
            'telefono': request.POST.get('telefono', '').strip(),
            'direccion': request.POST.get('direccion', '').strip(),
            'municipio': request.POST.get('municipio', '').strip(),
            'horarios': request.POST.get('horarios', '').strip(),
            'codigo_postal': request.POST.get('codigo_postal', '').strip(),
            'estado': request.POST.get('estado', '').strip(),
            'localidad': request.POST.get('localidad', '').strip(),
            'colonia': request.POST.get('colonia', '').strip(),
            'descripcion_publica': request.POST.get('descripcion_publica', '').strip(),
            'correo_publico': request.POST.get('correo_publico', '').strip(),
            'email': email,
            'tipo': request.POST.get('tipo', tipo),
            'dias_semana': dias_semana,
            'materiales_seleccionados': materiales_seleccionados
        })
        
        tipo = form_data.get('tipo', 'usuario')
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        terms = request.POST.get('terms')
        
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        responsable = request.POST.get('responsable', '').strip()
        nombre_centro = request.POST.get('nombre_centro', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        municipio = request.POST.get('municipio', '').strip()
        horarios = request.POST.get('horarios', '').strip()
        codigo_postal = request.POST.get('codigo_postal', '').strip()
        estado = request.POST.get('estado', '').strip()
        localidad = request.POST.get('localidad', '').strip()
        colonia = request.POST.get('colonia', '').strip()
        descripcion_publica = request.POST.get('descripcion_publica', '').strip()
        correo_publico = request.POST.get('correo_publico', '').strip()

        # Validaciones comunes
        if not email:
            error = 'Se requiere correo electrónico.'
        elif not is_valid_email(email):
            error = 'Correo electrónico no válido.'
        elif not password:
            error = 'Se requiere contraseña.'
        elif len(password) < 6:
            error = 'La contraseña debe tener al menos 6 caracteres.'
        elif len(password) > 128:
            error = 'La contraseña no puede superar los 128 caracteres.'
        elif password != password2:
            error = 'Las contraseñas no coinciden.'
        elif not terms:
            error = 'Debes aceptar los términos y condiciones.'
        elif tipo == 'usuario' and not nombre:
            error = 'Ingresa tu nombre.'
        elif tipo == 'usuario' and not apellido:
            error = 'Ingresa tu apellido.'
        elif tipo == 'centro' and not nombre_centro:
            error = 'Ingresa el nombre del centro.'
        elif tipo == 'centro' and not telefono:
            error = 'Ingresa el teléfono del centro.'
        elif tipo == 'centro' and not direccion:
            error = 'Ingresa la dirección del centro.'
        elif tipo == 'centro' and not municipio:
            error = 'Ingresa el municipio del centro.'
        elif tipo == 'centro' and not responsable:
            error = 'Ingresa el nombre del responsable del centro.'
        elif tipo == 'centro' and not nombre_centro:
            error = 'Ingresa el nombre del centro.'
        elif tipo == 'centro' and not telefono:
            error = 'Ingresa el teléfono del centro.'
        elif tipo == 'centro' and not direccion:
            error = 'Ingresa la dirección del centro.'
        elif tipo == 'centro' and not municipio:
            error = 'Ingresa el municipio del centro.'
        elif tipo == 'centro' and not horarios:
            error = 'Ingresa los horarios del centro.'
        else:
            User = get_user_model()
            if User.objects.filter(email__iexact=email).exists():
                error = 'Ya existe una cuenta local con ese correo.'
            else:
                # Verificar duplicado en Supabase perfiles por correo
                try:
                    perfil_resp = supa.client.table('perfiles').select('id').eq('correo', email).limit(1).execute()
                    if getattr(perfil_resp, 'data', None):
                        error = 'Ya existe una cuenta con ese correo en Supabase. Inicia sesión.'
                    centro_resp = supa.client.table('centros_acopio').select('id').eq('correo_contacto', email).limit(1).execute()
                    if getattr(centro_resp, 'data', None):
                        error = 'Ya existe un centro con ese correo. Inicia sesión.'
                except Exception:
                    pass

                if not error:
                        supa_user_id = None
                        created_django_user = None
                        if tipo == 'centro':
                            signup = supa.sign_up(email, password)
                            if getattr(signup, 'error', None):
                                err = signup.error or ''
                                low = err.lower() if isinstance(err, str) else ''
                                if 'already registered' in low or 'duplicate' in low or 'already exists' in low:
                                    error = 'El correo ya está registrado en Supabase. Inicia sesión para continuar.'
                                else:
                                    error = f'Error al crear usuario en Supabase: {err}'
                                raise Exception(error)

                            data = getattr(signup, 'data', None) or {}
                            user_info = None
                            if isinstance(data, dict):
                                user_info = data.get('user') or data.get('data') or data

                            if isinstance(user_info, dict):
                                supa_user_id = user_info.get('id') or user_info.get('user_id')
                            elif isinstance(data, dict):
                                supa_user_id = data.get('id')

                            if not supa_user_id:
                                error = 'No se obtuvo el ID de usuario desde Supabase. Intenta nuevamente.'
                                raise Exception(error)

                        # Crear usuario Django local para control de sesión en el sitio
                        created_django_user = User.objects.create_user(username=email, email=email, password=password)
                        login(request, created_django_user, backend='django.contrib.auth.backends.ModelBackend')
                        success = True

                        if tipo == 'centro':
                            if not supa_user_id:
                                raise Exception('No se pudo obtener el ID de usuario de Supabase para crear el centro.')

                            # Crear perfil en Supabase (id igual al id de auth)
                            try:
                                perfil_data = {
                                    'id': supa_user_id,
                                    'nombre': nombre_centro,
                                    'apellido': responsable,
                                    'telefono': telefono,
                                    'correo': email,
                                    'tipo_usuario': 'centro',
                                    'eco_puntos_saldo': 0,
                                    'estado_cuenta': True,
                                }
                                supa.client.table('perfiles').insert(perfil_data).execute()
                            except Exception:
                                pass

                            # También crear registro local de perfil para Django (opcional)
                            try:
                                perfil = PerfilFirebase.objects.create(
                                    id=uuid.UUID(supa_user_id),
                                    nombre=nombre_centro,
                                    apellido=responsable,
                                    telefono=telefono,
                                    correo=email,
                                    tipo_usuario='centro',
                                    eco_puntos_saldo=0,
                                    estado_cuenta=True
                                )
                            except Exception:
                                perfil = None

                            texto_descripcion = f"Responsable: {responsable}. {descripcion_publica or ''}"

                            # Horarios del formulario (para guardar en Supabase) -- evitar variable no definida
                            dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                            horarios_guardar = []
                            for i, dia in enumerate(dias, start=1):
                                apertura = request.POST.get(f'apertura_{i}', '').strip()
                                cierre = request.POST.get(f'cierre_{i}', '').strip()
                                activo = bool(request.POST.get(f'activo_{i}', 'on'))
                                if apertura and cierre and activo:
                                    horarios_guardar.append({
                                        'dia_semana': i,
                                        'hora_apertura': apertura,
                                        'hora_cierre': cierre,
                                    })

                            # Intentar geocodificar la dirección para mapear el centro.
                            geo = obtener_coordenadas_desde_direccion(f"{direccion}, {municipio}, Yucatán, México")
                            if geo is None:
                                geo = {'lat': 20.9674, 'lon': -89.6237}
                            latitud = geo['lat'] if geo else None
                            longitud = geo['lon'] if geo else None

                            centro_payload = {
                                'id_usuario': supa_user_id,
                                'nombre_comercial': nombre_centro,
                                'descripcion': texto_descripcion,
                                'direccion_texto': direccion,
                                'telefono_contacto': telefono,
                                'correo_contacto': correo_publico or email,
                                'estado_operativo': False,
                                'validado': False,
                            }
                            if latitud is not None and longitud is not None:
                                centro_payload['latitud'] = latitud
                                centro_payload['longitud'] = longitud

                            created_centro_resp = supa.client.table('centros_acopio').insert(centro_payload).execute()
                            centro_data = None
                            centro_id = None
                            created_centro_debug = {
                                'error': getattr(created_centro_resp, 'error', None),
                                'data': getattr(created_centro_resp, 'data', None)
                            }

                            if isinstance(created_centro_resp.data, list) and len(created_centro_resp.data) > 0:
                                centro_data = created_centro_resp.data[0]
                                centro_id = centro_data.get('id')
                            elif isinstance(created_centro_resp.data, dict):
                                centro_data = created_centro_resp.data
                                centro_id = centro_data.get('id')

                            if centro_id is None:
                                try:
                                    query_resp = supa.client.table('centros_acopio').select('*').eq('id_usuario', supa_user_id).eq('nombre_comercial', nombre_centro).order('created_at', desc=True).limit(1).execute()
                                    if hasattr(query_resp, 'data') and isinstance(query_resp.data, list) and len(query_resp.data) > 0:
                                        centro_data = query_resp.data[0]
                                        centro_id = centro_data.get('id')
                                except Exception:
                                    pass

                            if centro_id is None:
                                err_text = 'No se pudo crear el centro en Supabase.'
                                if created_centro_debug.get('error'):
                                    err_text += f" Error: {created_centro_debug.get('error')}"
                                err_text += f" Response: {created_centro_debug.get('data')}"
                                raise Exception(err_text)

                        # Guardar horarios en Supabase
                        try:
                            for h in horarios_guardar:
                                supa.client.table('centros_horarios').insert({
                                    'id_centro': centro_id,
                                    'dia_semana': h['dia_semana'],
                                    'hora_apertura': h['hora_apertura'],
                                    'hora_cierre': h['hora_cierre'],
                                }).execute()
                        except Exception:
                            pass

                        # Guardar materiales en Supabase
                        try:
                            materiales_post = request.POST.getlist('materiales')
                            for mid in materiales_post:
                                supa.client.table('centros_materiales').insert({
                                    'id_centro': centro_id,
                                    'id_material': mid,
                                }).execute()
                                supa.client.table('precios_centro').insert({
                                    'id_centro': centro_id,
                                    'id_material': mid,
                                    'precio_compra_actual': 0.0,
                                }).execute()
                        except Exception:
                            pass

                        # Subir foto de centro si existe y actualizar URL
                        if request.FILES.get('foto'):
                            try:
                                foto_archivo = request.FILES.get('foto')
                                foto_url = supa.upload_image(
                                    bucket='centros',
                                    user_id=supa_user_id,
                                    file=foto_archivo,
                                    folder='',
                                    custom_filename=f'centro_{centro_id}_{uuid.uuid4().hex}.jpg'
                                )
                                if foto_url:
                                    supa.client.table('centros_acopio').update({'url_foto_portada': foto_url}).eq('id', centro_id).execute()
                                    supa.client.table('perfiles').update({'imagen_url': foto_url}).eq('id', supa_user_id).execute()
                                    if centro_data is not None:
                                        centro_data['url_foto_portada'] = foto_url
                            except Exception:
                                pass

                        # Para la plantilla de centro_pendiente, usar el dict del supa
                        if tipo == 'centro':
                            centro = centro_data or {
                                'id': centro_id,
                                'nombre_comercial': nombre_centro,
                                'direccion_texto': direccion,
                                'telefono_contacto': telefono,
                                'correo_contacto': correo_publico or email,
                                'url_foto_portada': None,
                                'validado': False,
                                'estado_operativo': False,
                            }
                            messages.success(request, 'Registro completado! Tu centro se ha creado y está pendiente de validación.')
                            return render(request, 'centro_pendiente.html', {'centro': centro})
                        else:
                            request.session['usuario_nombre'] = nombre
                            request.session['usuario_apellido'] = apellido
                            return redirect('completar_registro')
                # if not error


    return render(request, 'register_screen.html', {
        'error': error,
        'tipo': tipo,
        'success': success,
        'form_data': form_data,
        'materiales': materiales,
        'dias_semana': form_data.get('dias_semana', [
            {'nombre':'Lunes','apertura':'08:00','cierre':'18:00','activo':True},
            {'nombre':'Martes','apertura':'08:00','cierre':'18:00','activo':True},
            {'nombre':'Miércoles','apertura':'08:00','cierre':'18:00','activo':True},
            {'nombre':'Jueves','apertura':'08:00','cierre':'18:00','activo':True},
            {'nombre':'Viernes','apertura':'08:00','cierre':'18:00','activo':True},
            {'nombre':'Sábado','apertura':'09:00','cierre':'14:00','activo':True},
            {'nombre':'Domingo','apertura':'09:00','cierre':'14:00','activo':True}
        ])
    })


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
        eventos = resp.data if isinstance(resp.data, list) else []
    except Exception as e:
        eventos = []
    return render(request, 'eventos.html', {'eventos': eventos})


# ─────────────────────────────────────────────
# PERFIL DE USUARIO
# ─────────────────────────────────────────────

@login_required
def perfil(request):
    # Obtener el tipo de usuario de la sesión (guardado en login)
    tipo_usuario = request.session.get('user_type', 'usuario')
    if tipo_usuario == 'centro':
        return redirect('perfil_centro')

    usuario = request.user
    supa = SupabaseClient()

    perfil_data = {}
    avatar_url = None
    qr_url = None
    puntos = 0
    try:
        url = f"{supa.url}/rest/v1/perfiles?correo=eq.{quote_plus(usuario.email)}"
        headers = {
            'apikey': supa.key,
            'Authorization': f'Bearer {supa.key}'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                perfil_data = data[0] if isinstance(data[0], dict) else {}
                avatar_url = perfil_data.get('imagen_url')
                qr_value = perfil_data.get('qr_codigo')
                puntos = perfil_data.get('eco_puntos_saldo', 0) or 0
                if not qr_value:
                    # Generar un QR local similar a la app y guardar en Supabase.
                    prefix = str(perfil_data.get('id', usuario.id)).replace('-', '')[:8]
                    ts = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
                    qr_value = f"QR_{prefix}_{ts}"
                    try:
                        update_resp = requests.patch(
                            f"{supa.url}/rest/v1/perfiles?id=eq.{quote_plus(str(perfil_data.get('id', '')))}",
                            headers={
                                'apikey': supa.key,
                                'Authorization': f'Bearer {supa.key}',
                                'Content-Type': 'application/json',
                                'Prefer': 'return=minimal',
                            },
                            json={'qr_codigo': qr_value},
                            timeout=10,
                        )
                        pass
                    except Exception:
                        pass

                # Generar URL de imagen de QR usando un servicio activo
                qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=280x280&data={quote_plus(str(qr_value))}"
                qr_alt_text = f"QR {qr_value}"
            else:
                pass
        else:
            pass
    except Exception:
        pass

    canjes = []
    total_canjes = 0
    try:
        perfil_id = perfil_data.get('id')
        # aceptar fallback de id de usuario desde sesión (para casos de login con allauth)
        fallback_id = request.session.get('user_id_supabase')
        canjes_raw = []
        if perfil_id:
            canjes_resp = requests.get(
                f"{supa.url}/rest/v1/canjes?order=fecha_canje.desc&limit=20&id_usuario=eq.{quote_plus(str(perfil_id))}",
                headers=headers,
                timeout=10,
            )
            if canjes_resp.status_code == 200:
                canjes_raw = canjes_resp.json() if isinstance(canjes_resp.json(), list) else []

        if not canjes_raw and fallback_id and fallback_id != perfil_id:
            canjes_resp = requests.get(
                f"{supa.url}/rest/v1/canjes?order=fecha_canje.desc&limit=20&id_usuario=eq.{quote_plus(str(fallback_id))}",
                headers=headers,
                timeout=10,
            )
            if canjes_resp.status_code == 200:
                canjes_raw = canjes_resp.json() if isinstance(canjes_resp.json(), list) else []

        if not canjes_raw:
            # último fallback a todos los canjes con filtro por correo en perfil (si existe)
            if perfil_data.get('correo'):
                canjes_resp = requests.get(
                    f"{supa.url}/rest/v1/canjes?order=fecha_canje.desc&limit=20&select=*&id_usuario=eq.{quote_plus(str(perfil_id))}",
                    headers=headers,
                    timeout=10,
                )
                if canjes_resp.status_code == 200:
                    canjes_raw = canjes_resp.json() if isinstance(canjes_resp.json(), list) else []

        # Fallback adicional: usar transacciones si no hay canjes registrados
        if not canjes_raw and perfil_id:
            trans_resp = requests.get(
                f"{supa.url}/rest/v1/transacciones?order=fecha_transaccion.desc&limit=20&id_usuario=eq.{quote_plus(str(perfil_id))}",
                headers=headers,
                timeout=10,
            )
            if trans_resp.status_code == 200:
                trans_data = trans_resp.json() if isinstance(trans_resp.json(), list) else []
                if isinstance(trans_data, list) and trans_data:
                    canjes_raw = []
                    for item in trans_data:
                        if not isinstance(item, dict):
                            continue
                        pts = item.get('total_puntos_ganados') or item.get('puntos') or 0
                        fecha = item.get('fecha_transaccion') or item.get('created_at') or item.get('fecha') or ''
                        canjes_raw.append({
                            'tipo_recompensa': 'Transacción de reciclaje',
                            'monto_puntos_restados': pts,
                            'fecha_canje': fecha,
                            'descripcion': item.get('detalle', 'Reciclaje registrado'),
                        })

        if isinstance(canjes_raw, list):
            if canjes_raw:
                for record in canjes_raw:
                    if not isinstance(record, dict):
                        continue
                premio_title = (
                    record.get('tipo_recompensa')
                    or record.get('premio_nombre')
                    or record.get('premio')
                    or record.get('recompensa_nombre')
                    or record.get('descripcion')
                    or 'Canje'
                )
                premio_cost = (
                    record.get('monto_puntos_restados')
                    or record.get('puntos_usados')
                    or record.get('puntos')
                    or record.get('eco_puntos')
                    or record.get('monto')
                    or 0
                )
                fecha = (
                    record.get('fecha_canje')
                    or record.get('created_at')
                    or record.get('updated_at')
                    or record.get('fecha')
                    or ''
                )
                detalle = (
                    record.get('descripcion')
                    or record.get('texto')
                    or record.get('nota')
                    or record.get('tipo_recompensa')
                    or ''
                )
                canjes.append({
                    'premio': {
                        'title': premio_title,
                        'points_cost': premio_cost,
                    },
                    'created_at': fecha,
                    'puntos': premio_cost,
                    'texto': detalle,
                    'tipo_recompensa': record.get('tipo_recompensa'),
                    'monto_puntos_restados': record.get('monto_puntos_restados'),
                    'fecha': fecha,
                    'detalle': detalle,
                })
            total_canjes = len(canjes)
    except Exception:
        pass

    # Recortar últimos 5 para el panel
    ultimos_canjes = canjes[:5]

    context = {
        'usuario': {
            'username': usuario.username,
            'first_name': perfil_data.get('nombre', usuario.first_name) if perfil_data else usuario.first_name,
            'last_name': perfil_data.get('apellido', usuario.last_name) if perfil_data else usuario.last_name,
            'email': usuario.email,
            'phone': perfil_data.get('telefono', '') if perfil_data else '',
            'avatar_url': avatar_url,
            'qr_codigo': qr_url,
            'points': puntos,
        },
        'total_canjes': total_canjes,
        'ultimos_canjes': ultimos_canjes,
        'qr_url': qr_url,
    }
    return render(request, 'perfil_usuario.html', context)


@login_required
def api_perfil(request):
    """Endpoint JSON: devuelve el perfil del usuario autenticado desde Supabase."""
    usuario = request.user
    supa = SupabaseClient()
    try:
        resp = supa.client.table('perfiles').select('*').eq('correo', usuario.email).execute()
        perfil = None
        if isinstance(resp.data, list) and len(resp.data) > 0:
            perfil = resp.data[0] if isinstance(resp.data[0], dict) else None
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
        perfil = None
        if isinstance(resp.data, list) and len(resp.data) > 0:
            perfil = resp.data[0] if isinstance(resp.data[0], dict) else None
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
    """Panel sencillo para administradores: listar centros pendientes desde Supabase y gestionar eventos/premios."""
    supa = SupabaseClient()
    pending_centros = []
    approved_centros = []
    eventos = []
    premios = []

    # Manejo de formularios POST para crear/eliminar eventos y premios.
    if request.method == 'POST':
        panel_action = request.POST.get('panel_action')
        try:
            if panel_action == 'crear_evento':
                titulo = request.POST.get('titulo_evento', '').strip()
                descripcion_evento = request.POST.get('descripcion_evento', '').strip()
                fecha_evento = request.POST.get('fecha_evento', '').strip()
                link_evento = request.POST.get('link_evento', '').strip()
                imagen_file = request.FILES.get('imagen_evento')
                imagen_url = None
                if imagen_file:
                    imagen_url = supa.upload_image(
                        bucket='eventos',
                        user_id=str(request.user.id),
                        file=imagen_file,
                        folder='eventos/',
                        custom_filename=f"evento_{uuid.uuid4().hex}.jpg"
                    )
                evento_payload = {
                    'titulo': titulo,
                    'descripcion': descripcion_evento,
                    'fecha_evento': fecha_evento or datetime.now().isoformat(),
                    'ubicacion': '',
                    'imagen_url': imagen_url,
                    'link': link_evento,
                }
                supa.client.table('eventos').insert(evento_payload).execute()
                messages.success(request, 'Evento creado con éxito.')
            elif panel_action == 'eliminar_evento':
                evento_id = request.POST.get('evento_id')
                if evento_id:
                    supa.client.table('eventos').delete().eq('id', int(evento_id)).execute()
                    messages.success(request, 'Evento eliminado.')
            elif panel_action == 'crear_premio':
                nombre = request.POST.get('nombre_premio', '').strip()
                descripcion_premio = request.POST.get('descripcion_premio', '').strip()
                puntos = request.POST.get('puntos_premio', '').strip()
                disponible = bool(request.POST.get('disponible_premio'))
                imagen_file = request.FILES.get('imagen_premio')
                imagen_url = None
                if imagen_file:
                    imagen_url = supa.upload_image(
                        bucket='recompensas',
                        user_id=str(request.user.id),
                        file=imagen_file,
                        folder='recompensas/',
                        custom_filename=f"premio_{uuid.uuid4().hex}.jpg"
                    )
                premio_payload = {
                    'nombre': nombre,
                    'descripcion': descripcion_premio,
                    'puntos_requeridos': int(puntos) if puntos.isdigit() else 0,
                    'imagen_url': imagen_url,
                    'disponible': disponible,
                }
                supa.client.table('recompensas').insert(premio_payload).execute()
                messages.success(request, 'Premio creado correctamente.')
            elif panel_action == 'eliminar_premio':
                premio_id = request.POST.get('premio_id')
                if premio_id:
                    supa.client.table('recompensas').delete().eq('id', int(premio_id)).execute()
                    messages.success(request, 'Premio eliminado.')
        except Exception as e:
            messages.error(request, f'Error en acción de panel: {str(e)}')

    try:
        resp_pending = (
            supa.client.table('centros_acopio')
            .select('*')
            .eq('validado', False)
            .order('created_at', desc=False)
            .execute()
        )
        pending_centros = resp_pending.data if resp_pending and getattr(resp_pending, 'data', None) else []
    except Exception:
        pending_centros = []

    try:
        resp_approved = (
            supa.client.table('centros_acopio')
            .select('*')
            .eq('validado', True)
            .order('created_at', desc=False)
            .execute()
        )
        approved_centros = resp_approved.data if resp_approved and getattr(resp_approved, 'data', None) else []
    except Exception:
        approved_centros = []

    try:
        resp_eventos = (
            supa.client.table('eventos')
            .select('*')
            .order('fecha_evento', desc=False)
            .execute()
        )
        eventos = resp_eventos.data if resp_eventos and getattr(resp_eventos, 'data', None) else []
    except Exception:
        eventos = []

    try:
        resp_premios = (
            supa.client.table('recompensas')
            .select('*')
            .order('created_at', desc=False)
            .execute()
        )
        premios = resp_premios.data if resp_premios and getattr(resp_premios, 'data', None) else []
    except Exception:
        premios = []

    # Normalizar claves para facilitar el template
    for c in pending_centros + approved_centros:
        if 'name' not in c:
            c['name'] = c.get('nombre_comercial')
        if 'address' not in c:
            c['address'] = c.get('direccion_texto')
        if 'contact_email' not in c:
            c['contact_email'] = c.get('correo_contacto')
        if 'latitude' not in c:
            c['latitude'] = c.get('latitud')
        if 'longitude' not in c:
            c['longitude'] = c.get('longitud')
        if 'correo' not in c:
            c['correo'] = c.get('correo_contacto')

    return render(request, 'admin_centros.html', {
        'pending_centros': pending_centros,
        'approved_centros': approved_centros,
        'eventos': eventos,
        'premios': premios,
    })


@staff_member_required
def admin_centros_accion(request):
    """Recibe POST con 'centro_id' y 'accion' ('aprobar'|'rechazar') y actualiza Supabase."""
    if request.method != 'POST':
        return HttpResponseForbidden()

    centro_id = request.POST.get('centro_id')
    accion = request.POST.get('accion')
    if not centro_id or accion not in ('aprobar', 'rechazar', 'eliminar'):
        return redirect('admin_centros')

    supa = SupabaseClient()
    try:
        if accion == 'aprobar':
            update = {'validado': True, 'estado_operativo': True}
            supa.client.table('centros_acopio').update(update).eq('id', int(centro_id)).execute()
            messages.success(request, 'Centro aprobado correctamente.')
        elif accion == 'rechazar':
            try:
                centro_resp = supa.client.table('centros_acopio').select('*').eq('id', centro_id).execute()
                centro = centro_resp.data[0] if centro_resp and getattr(centro_resp, 'data', None) and len(centro_resp.data) > 0 else None
                id_usuario = centro.get('id_usuario') if isinstance(centro, dict) else None

                supa.client.table('centros_horarios').delete().eq('id_centro', centro_id).execute()
                supa.client.table('centros_materiales').delete().eq('id_centro', centro_id).execute()
                supa.client.table('precios_centro').delete().eq('id_centro', centro_id).execute()
                supa.client.table('centros_acopio').delete().eq('id', centro_id).execute()
                if id_usuario:
                    supa.client.table('perfiles').delete().eq('id', id_usuario).execute()
                messages.success(request, 'Centro rechazado y datos relacionados borrados.')
            except Exception as e:
                messages.error(request, f'Error al rechazar el centro: {str(e)}')
        elif accion == 'eliminar':
            try:
                centro_resp = supa.client.table('centros_acopio').select('*').eq('id', centro_id).execute()
                centro = centro_resp.data[0] if centro_resp and getattr(centro_resp, 'data', None) and len(centro_resp.data) > 0 else None
                id_usuario = centro.get('id_usuario') if isinstance(centro, dict) else None

                supa.client.table('centros_horarios').delete().eq('id_centro', centro_id).execute()
                supa.client.table('centros_materiales').delete().eq('id_centro', centro_id).execute()
                supa.client.table('precios_centro').delete().eq('id_centro', centro_id).execute()
                supa.client.table('centros_acopio').delete().eq('id', centro_id).execute()
                if id_usuario:
                    supa.client.table('perfiles').delete().eq('id', id_usuario).execute()
                messages.success(request, 'Centro eliminado y datos relacionados borrados.')
            except Exception as e:
                messages.error(request, f'Error al eliminar el centro: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error en acción de centro: {str(e)}')

    return redirect('admin_centros')


def api_centros(request):
    """Endpoint público que devuelve centros aprobados/validados desde Supabase en JSON."""
    supa = SupabaseClient()
    try:
        # No filtrar por 'validado' aquí: muchos centros en Supabase aún no están validados.
        # Devolvemos todos y la plantilla/JS decide cómo mostrarlos.
        resp = supa.client.table('centros_acopio').select('*').execute()
        centros = resp.data if resp and getattr(resp, 'data', None) else []
        
        # Asegurar que centros sea una lista y contenga dicts, no strings
        if not isinstance(centros, list):
            centros = []
        centros = [c for c in centros if isinstance(c, dict)]
        
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
        
        # Asegurar que premios sea una lista y contenga dicts, no strings
        if not isinstance(premios, list):
            premios = []
        premios = [p for p in premios if isinstance(p, dict)]
    except Exception as e:
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


@login_required
def editar_perfil(request):
    usuario = request.user
    supa = SupabaseClient()
    
    # ========================================
    # 1. OBTENER PERFIL DE SUPABASE
    # ========================================
    perfil_id = None
    try:
        # Consulta directa a Supabase
        url = f"{supa.url}/rest/v1/perfiles?correo=eq.{quote_plus(usuario.email)}&select=id"
        headers = {
            'apikey': supa.key,
            'Authorization': f'Bearer {supa.key}'
        }
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                perfil_id = data[0].get('id')
        else:
            pass
    except Exception:
        pass
    
    if request.method == 'POST':
        # ========================================
        # 2. PROCESAR FORMULARIO
        # ========================================
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        telefono = request.POST.get('phone', '').strip()
        
        # Actualizar Django
        if nombre:
            usuario.first_name = nombre
        if apellido:
            usuario.last_name = apellido
        usuario.save()
        
        # Preparar datos
        datos_actualizar = {}
        if nombre:
            datos_actualizar['nombre'] = nombre
        if apellido:
            datos_actualizar['apellido'] = apellido
        if telefono:
            datos_actualizar['telefono'] = telefono
        
        # ========================================
        # 3. PROCESAR IMAGEN
        # ========================================
        if 'avatar' in request.FILES:
            imagen_file = request.FILES['avatar']
            
            # Subir a Storage
            imagen_url = supa.upload_image(
                bucket='avatars',
                user_id=str(usuario.id),
                file=imagen_file,
                folder='usuarios'
            )
            
            if imagen_url:
                datos_actualizar['imagen_url'] = imagen_url
                messages.success(request, '✅ Foto subida correctamente')

        # ========================================
        # 4. ACTUALIZAR EN SUPABASE (MÉTODO DIRECTO)
        # ========================================
        if datos_actualizar and perfil_id:
            try:
                # URL directa para actualizar
                update_url = f"{supa.url}/rest/v1/perfiles?id=eq.{quote_plus(str(perfil_id))}"
                
                headers_update = {
                    'apikey': supa.key,
                    'Authorization': f'Bearer {supa.key}',
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal'  # No esperar respuesta
                }
                
                response = requests.patch(update_url, headers=headers_update, json=datos_actualizar)
                
                if response.status_code in (200, 204):
                    messages.success(request, '✅ Perfil actualizado en Supabase')
                else:
                    messages.error(request, f'❌ Error {response.status_code} en Supabase')
            except Exception as e:
                messages.error(request, f'❌ Error: {str(e)}')
        else:
            if not perfil_id:
                messages.error(request, '❌ No se encontró tu perfil')
            if not datos_actualizar:
                messages.info(request, 'ℹ️ No hay cambios')
        
        return redirect('perfil')
    
    # ========================================
    # 5. PREPARAR CONTEXTO PARA EL TEMPLATE
    # ========================================
    context = {
        'usuario': {
            'first_name': usuario.first_name,
            'last_name': usuario.last_name,
            'email': usuario.email,
            'phone': usuario.phone if hasattr(usuario, 'phone') else '',
            'avatar': '',  # No cargamos avatar aquí por simplicidad
        }
    }
    
    return render(request, 'editar_perfil.html', context)


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
            .execute()
        )
        if perfil_resp and getattr(perfil_resp, 'data', None):
            data = perfil_resp.data
            if isinstance(data, list) and len(data) > 0:
                perfil_id = data[0].get('id')
            elif isinstance(data, dict):
                perfil_id = data.get('id')
    except Exception as e:
        perfil_id = None

    # Si no hay perfil en `perfiles`, intentar con Firebase UID (campo firebase_uid)
    if not perfil_id:
        try:
            perfil_resp = (
                supa.client.table('perfiles')
                .select('id')
                .eq('firebase_uid', usuario.email)
                .execute()
            )
            if perfil_resp and getattr(perfil_resp, 'data', None):
                data = perfil_resp.data
                if isinstance(data, list) and len(data) > 0:
                    perfil_id = data[0].get('id')
                elif isinstance(data, dict):
                    perfil_id = data.get('id')
        except Exception as e:
            perfil_id = None

    if perfil_id:
        try:
            raw_canjes = []
            # Query principal por id_usuario
            resp = (
                supa.client.table('canjes')
                .select('*')
                .eq('id_usuario', perfil_id)
                .order('fecha_canje', desc=True)
                .execute()
            )
            if hasattr(resp, 'data') and isinstance(resp.data, list):
                raw_canjes = resp.data
            if not raw_canjes:
                # Try logging first 2 canjes just to inspect
                all_resp = supa.client.table('canjes').select('*').order('fecha_canje', desc=True).limit(5).execute()

            # Fallback: si no hay canjes, intentar consultar con id_usuario obtenido de sesión
            if not raw_canjes:
                fallback_user_id = request.session.get('user_id_supabase')
                if fallback_user_id and fallback_user_id != perfil_id:
                    resp2 = (
                        supa.client.table('canjes')
                        .select('*')
                        .eq('id_usuario', fallback_user_id)
                        .order('fecha_canje', desc=True)
                        .execute()
                    )
                    if isinstance(resp2.data, list):
                        raw_canjes = resp2.data

            total_puntos_usados = sum(c.get('monto_puntos_restados', 0) for c in raw_canjes if isinstance(c, dict))
            for c in raw_canjes:
                if not isinstance(c, dict):
                    continue
                title = (
                    c.get('tipo_recompensa')
                    or c.get('premio')
                    or c.get('descripcion')
                    or 'Canje'
                )
                points_cost = (
                    c.get('monto_puntos_restados')
                    or c.get('puntos_usados')
                    or c.get('puntos')
                    or 0
                )
                canjes.append({
                    'premio': {
                        'title': title,
                        'points_cost': points_cost,
                    },
                    'quantity': 1,
                    'created_at': c.get('fecha_canje') or c.get('created_at') or c.get('fecha'),
                    'fulfilled': c.get('estado') == 'exitoso',
                    'detalle': c.get('descripcion') or c.get('detalle') or '',
                })
        except Exception as e:
            canjes = []
            total_puntos_usados = 0

    return render(request, 'historial_canjes.html', {
        'canjes': canjes,
        'total_puntos_usados': total_puntos_usados,
    })


@login_required
def sincronizar_qr(request):
    usuario = request.user
    supa = SupabaseClient()
    qr_value = None
    try:
        perfil_resp = (
            supa.client.table('perfiles')
            .select('id, qr_codigo')
            .eq('correo', usuario.email)
            .single()
            .execute()
        )
        perfil = perfil_resp.data if perfil_resp and perfil_resp.data else {}
        perfil_id = perfil.get('id') if isinstance(perfil, dict) else None
        if perfil_id:
            prefix = str(perfil_id).replace('-', '')[:8]
            ts = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')
            qr_value = f"QR_{prefix}_{ts}"
            update_resp = requests.patch(
                f"{supa.url}/rest/v1/perfiles?id=eq.{quote_plus(str(perfil_id))}",
                headers={
                    'apikey': supa.key,
                    'Authorization': f'Bearer {supa.key}',
                    'Content-Type': 'application/json',
                    'Prefer': 'return=minimal',
                },
                json={'qr_codigo': qr_value},
                timeout=10,
            )
            if update_resp.status_code in (200, 204):
                messages.success(request, '✅ QR sincronizado correctamente.')
            else:
                messages.error(request, '❌ No se pudo sincronizar QR. Intente más tarde.')
        else:
            messages.error(request, '❌ No se encontró perfil para sincronizar QR.')
    except Exception:
        messages.error(request, '❌ Error al sincronizar QR.')
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
        perfil_id = None

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
            mis_sugerencias = resp.data if isinstance(resp.data, list) else []
        except Exception as e:
            mis_sugerencias = []

    return render(request, 'sugerencias.html', {'mis_sugerencias': mis_sugerencias})


# ─────────────────────────────────────────────
# PERFIL DE CENTRO
# ─────────────────────────────────────────────

@login_required
def perfil_centro(request):
    usuario = request.user
    supa = SupabaseClient()
    
    
    # ========================================
    # 1. OBTENER PERFIL DE SUPABASE
    # ========================================
    perfil_id = None
    perfil_data = None
    try:
        url_perfil = f"{supa.url}/rest/v1/perfiles?correo=eq.{quote_plus(usuario.email)}"
        headers = {
            'apikey': supa.key,
            'Authorization': f'Bearer {supa.key}'
        }
        response_perfil = requests.get(url_perfil, headers=headers)
        
        if response_perfil.status_code == 200:
            perfiles = response_perfil.json()
            if perfiles and len(perfiles) > 0:
                perfil_data = perfiles[0]
                perfil_id = perfil_data.get('id')
    except Exception:
        pass
    
    # ========================================
    # 2. OBTENER DATOS DEL CENTRO
    # ========================================
    centro_data = None
    eventos_centro = []
    horarios_centro = []
    
    if perfil_id:
        try:
            # Obtener datos del centro
            url_centro = f"{supa.url}/rest/v1/centros_acopio?id_usuario=eq.{quote_plus(str(perfil_id))}"
            response_centro = requests.get(url_centro, headers=headers)
            
            if response_centro.status_code == 200:
                centros = response_centro.json()
                if centros and len(centros) > 0:
                    centro_data = centros[0]
                    centro_id = centro_data.get('id')
                    # Centro encontrado
                    
                    # Obtener eventos del centro
                    url_eventos = f"{supa.url}/rest/v1/eventos?id_centro=eq.{quote_plus(str(centro_id))}&order=fecha_evento.desc"
                    response_eventos = requests.get(url_eventos, headers=headers)
                    
                    if response_eventos.status_code == 200:
                        eventos_centro = response_eventos.json()
                    
                    # Obtener horarios del centro
                    url_horarios = f"{supa.url}/rest/v1/centros_horarios?id_centro=eq.{quote_plus(str(centro_id))}&order=dia_semana.asc"
                    response_horarios = requests.get(url_horarios, headers=headers)
                    
                    if response_horarios.status_code == 200:
                        horarios_centro = response_horarios.json()
                        centro_data['horarios'] = horarios_centro
        except Exception:
            pass
    # ========================================
    # 3. PREPARAR CONTEXTO
    # ========================================
    context = {
        'centro': centro_data,
        'eventos': eventos_centro,
        'horarios': horarios_centro,
        'perfil': perfil_data,
        'tiene_centro': centro_data is not None,
    }
    
    return render(request, 'perfil_centro.html', context)


@login_required
def editar_perfil_centro(request):
    usuario = request.user
    supa = SupabaseClient()
    
    # ========================================
    # 1. OBTENER PERFIL Y CENTRO
    # ========================================
    perfil_id = None
    centro_data = None
    centro_id = None
    try:
        url_perfil = f"{supa.url}/rest/v1/perfiles?correo=eq.{quote_plus(usuario.email)}"
        headers = {
            'apikey': supa.key,
            'Authorization': f'Bearer {supa.key}'
        }
        response_perfil = requests.get(url_perfil, headers=headers)
        
        if response_perfil.status_code == 200:
            perfiles = response_perfil.json()
            if perfiles and len(perfiles) > 0:
                perfil_id = perfiles[0].get('id')
                
                # Obtener centro
                url_centro = f"{supa.url}/rest/v1/centros_acopio?id_usuario=eq.{quote_plus(str(perfil_id))}"
                response_centro = requests.get(url_centro, headers=headers)
                
                if response_centro.status_code == 200:
                    centros = response_centro.json()
                    if centros and len(centros) > 0:
                        centro_data = centros[0]
                        centro_id = centro_data.get('id')
                        
                        # Obtener horarios del centro
                        url_horarios = f"{supa.url}/rest/v1/centros_horarios?id_centro=eq.{quote_plus(str(centro_id))}"
                        response_horarios = requests.get(url_horarios, headers=headers)
                        if response_horarios.status_code == 200:
                            centro_data['horarios'] = response_horarios.json()
    except Exception as e:
        pass

    if request.method == 'POST':
       
        # Verificar específicamente el campo dirección
        direccion_recibida = request.POST.get('direccion', '')
        
        datos_actualizar = {}
        
        # 1. DATOS BÁSICOS DEL CENTRO
        nombre_centro = request.POST.get('nombre_centro', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        direccion_manual = request.POST.get('direccion', '').strip()
        
        if nombre_centro:
            datos_actualizar['nombre_comercial'] = nombre_centro
        if telefono:
            datos_actualizar['telefono_contacto'] = telefono
        
        # 2. COORDENADAS Y DIRECCIÓN AUTOMÁTICA
        latitud = request.POST.get('latitud', '').strip()
        longitud = request.POST.get('longitud', '').strip()
        
        
        if latitud and longitud:
            try:
                lat_float = float(latitud)
                lng_float = float(longitud)
                
                if 20.0 <= lat_float <= 22.0 and -91.0 <= lng_float <= -87.0:
                    datos_actualizar['latitud'] = lat_float
                    datos_actualizar['longitud'] = lng_float
                    
                    # Obtener dirección automática
                    direccion_auto = obtener_direccion_desde_coordenadas(lat_float, lng_float)
                    
                    if direccion_auto:
                        datos_actualizar['direccion_texto'] = direccion_auto
                        messages.success(request, '📍 Dirección obtenida automáticamente')
                    else:
                        if direccion_manual:
                            datos_actualizar['direccion_texto'] = direccion_manual
                else:
                    if direccion_manual:
                        datos_actualizar['direccion_texto'] = direccion_manual
                        
            except Exception as e:
                if direccion_manual:
                    datos_actualizar['direccion_texto'] = direccion_manual
        else:
            if direccion_manual:
                datos_actualizar['direccion_texto'] = direccion_manual
        
        # 3. ACTUALIZAR CENTRO
        if datos_actualizar and centro_id:
            update_url = f"{supa.url}/rest/v1/centros_acopio?id=eq.{quote_plus(str(centro_id))}"
            headers_update = {
                'apikey': supa.key,
                'Authorization': f'Bearer {supa.key}',
                'Content-Type': 'application/json',
                'Prefer': 'return=minimal'
            }
            response = requests.patch(update_url, headers=headers_update, json=datos_actualizar)
            if response.status_code in [200, 204]:
                messages.success(request, '✅ Datos del centro actualizados')
        
        # 4. PROCESAR HORARIOS
        if centro_id:
            # Eliminar horarios existentes
            del_url = f"{supa.url}/rest/v1/centros_horarios?id_centro=eq.{quote_plus(str(centro_id))}"
            requests.delete(del_url, headers=headers_update)
            
            # Insertar nuevos horarios
            dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
            horarios_guardados = 0
            for i, dia in enumerate(dias, 1):
                apertura = request.POST.get(f'apertura_{i}')
                cierre = request.POST.get(f'cierre_{i}')
                if apertura and cierre and apertura.strip() and cierre.strip():
                    nuevo_horario = {
                        'id_centro': centro_id,
                        'dia_semana': i,
                        'hora_apertura': apertura,
                        'hora_cierre': cierre
                    }
                    insert_url = f"{supa.url}/rest/v1/centros_horarios"
                    insert_response = requests.post(insert_url, headers=headers_update, json=nuevo_horario)
                    if insert_response.status_code == 201:
                        horarios_guardados += 1
            if horarios_guardados > 0:
                messages.success(request, f'✅ {horarios_guardados} horarios guardados')
        
        # 5. PROCESAR FOTO
        if 'foto' in request.FILES:
            foto_file = request.FILES['foto']
            if foto_file.content_type in ['image/jpeg', 'image/png']:
                BUCKET_NAME = 'centros'
                foto_url = supa.upload_image(
                    bucket=BUCKET_NAME,
                    user_id=str(usuario.id),
                    file=foto_file,
                    folder='',
                    custom_filename=f"centro_{usuario.id}.jpg"
                )
                if foto_url:
                    foto_update = {'url_foto_portada': foto_url}
                    update_url = f"{supa.url}/rest/v1/centros_acopio?id=eq.{quote_plus(str(centro_id))}"
                    headers_update = {
                        'apikey': supa.key,
                        'Authorization': f'Bearer {supa.key}',
                        'Content-Type': 'application/json',
                        'Prefer': 'return=minimal'
                    }
                    foto_response = requests.patch(update_url, headers=headers_update, json=foto_update)
                    if foto_response.status_code in [200, 204]:
                        messages.success(request, '✅ Foto actualizada')
        
        return redirect('perfil_centro')
    
    # Preparar días de la semana para el template
    dias_semana = [
        {'nombre': 'Lunes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Martes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Miércoles', 'apertura': '', 'cierre': ''},
        {'nombre': 'Jueves', 'apertura': '', 'cierre': ''},
        {'nombre': 'Viernes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Sábado', 'apertura': '', 'cierre': ''},
        {'nombre': 'Domingo', 'apertura': '', 'cierre': ''},
    ]
    
    # Si hay horarios guardados, llenar los campos
    if centro_data and centro_data.get('horarios'):
        for h in centro_data['horarios']:
            idx = h['dia_semana'] - 1
            if 0 <= idx < 7:
                dias_semana[idx]['apertura'] = h['hora_apertura']
                dias_semana[idx]['cierre'] = h['hora_cierre']
    
    context = {
        'centro': centro_data,
        'dias_semana': dias_semana,
    }
    return render(request, 'editar_perfil_centro.html', context)


# ─────────────────────────────────────────────
# FLUJO DE REGISTRO
# ─────────────────────────────────────────────

def completar_registro(request):
    if not request.user.is_authenticated:
        return redirect('/login-screen/')
    
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
        return redirect('/login-screen/')
    
    # Verificar si ya tiene perfil
    try:
        PerfilFirebase.objects.get(correo=request.user.email)
        messages.warning(request, 'Tu cuenta ya está configurada.')
        return redirect('home')
    except PerfilFirebase.DoesNotExist:
        pass
    
    # Obtener datos de la sesión (guardados en register_screen)
    nombre = request.session.pop('usuario_nombre', '')
    apellido = request.session.pop('usuario_apellido', '')
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', nombre).strip()
        last_name = request.POST.get('last_name', apellido).strip()
        telefono = request.POST.get('telefono', '').strip()
        
        # Crear perfil en Firebase
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
    
    return render(request, 'completar_usuario.html', {
        'nombre': nombre,
        'apellido': apellido
    })


def completar_centro(request):
    if not request.user.is_authenticated:
        return redirect('/login-screen/')
    
    # Verificar si ya tiene perfil
    try:
        PerfilFirebase.objects.get(correo=request.user.email)
        messages.warning(request, 'Tu cuenta ya está configurada.')
        return redirect('home')
    except PerfilFirebase.DoesNotExist:
        pass
    
    # Obtener datos guardados en sesión (desde register_screen)
    responsable = request.session.pop('centro_responsable', '')
    nombre_centro = request.session.pop('centro_nombre', '')
    telefono = request.session.pop('centro_telefono', '')
    direccion = request.session.pop('centro_direccion', '')
    municipio = request.session.pop('centro_municipio', '')
    horarios = request.session.pop('centro_horarios', '')
    
    # Campos adicionales nuevos
    codigo_postal = request.session.pop('centro_codigo_postal', '')
    estado = request.session.pop('centro_estado', '')
    localidad = request.session.pop('centro_localidad', '')
    colonia = request.session.pop('centro_colonia', '')
    descripcion_publica = request.session.pop('centro_descripcion_publica', '')
    correo_publico = request.session.pop('centro_correo_publico', '')
    dias_semana = request.session.pop('centro_dias_semana', [])
    materiales_seleccionados = request.session.pop('centro_materiales', [])

    if not dias_semana:
        dias_semana = [
            {'nombre': 'Lunes', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Martes', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Miércoles', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Jueves', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Viernes', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Sábado', 'apertura': '', 'cierre': '', 'activo': True},
            {'nombre': 'Domingo', 'apertura': '', 'cierre': '', 'activo': True},
        ]

    supa = SupabaseClient()
    materiales = []
    try:
        materiales = supa.obtener_materiales()
    except Exception:
        materiales = []
    if not materiales:
        materiales = [
            {'id': '1', 'nombre': 'Vidrio'},
            {'id': '2', 'nombre': 'Textiles'},
            {'id': '3', 'nombre': 'TetraPak'},
            {'id': '4', 'nombre': 'Plástico'},
            {'id': '5', 'nombre': 'Papel y cartón'}
        ]

    dias_semana = [
        {'nombre': 'Lunes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Martes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Miércoles', 'apertura': '', 'cierre': ''},
        {'nombre': 'Jueves', 'apertura': '', 'cierre': ''},
        {'nombre': 'Viernes', 'apertura': '', 'cierre': ''},
        {'nombre': 'Sábado', 'apertura': '', 'cierre': ''},
        {'nombre': 'Domingo', 'apertura': '', 'cierre': ''}
    ]
    if request.method == 'POST':
        # Usar datos de sesión o POST (permitir edición)
        responsable = request.POST.get('responsable', responsable).strip()
        nombre_centro = request.POST.get('nombre_centro', nombre_centro).strip()
        telefono = request.POST.get('telefono', telefono).strip()
        direccion = request.POST.get('direccion', direccion).strip()
        municipio = request.POST.get('municipio', municipio).strip()
        codigo_postal = request.POST.get('codigo_postal', codigo_postal).strip()
        estado = request.POST.get('estado', estado).strip()
        localidad = request.POST.get('localidad', localidad).strip()
        colonia = request.POST.get('colonia', colonia).strip()
        descripcion_publica = request.POST.get('descripcion_publica', descripcion_publica).strip()
        correo_publico = request.POST.get('correo_publico', correo_publico).strip()
        materiales_selectos = request.POST.getlist('materiales')

        # Horarios (solo si se envían)
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        horarios_guardar = []
        for i, dia in enumerate(dias, 1):
            apertura = request.POST.get(f'apertura_{i}', dias_semana[i - 1].get('apertura', '')).strip()
            cierre = request.POST.get(f'cierre_{i}', dias_semana[i - 1].get('cierre', '')).strip()
            activo = bool(request.POST.get(f'activo_{i}', 'on'))
            dias_semana[i-1]['apertura'] = apertura
            dias_semana[i-1]['cierre'] = cierre
            dias_semana[i-1]['activo'] = activo
            if apertura and cierre and activo:
                horarios_guardar.append({'dia_semana': i, 'dia_texto': dia, 'apertura': apertura, 'cierre': cierre})

        materiales_seleccionados = materiales_selectos if materiales_selectos else materiales_seleccionados

        if not responsable:
            messages.error(request, 'El nombre del responsable es obligatorio.')
        elif not nombre_centro:
            messages.error(request, 'El nombre del centro es obligatorio.')
        elif not telefono:
            messages.error(request, 'El teléfono del centro es obligatorio.')
        elif not direccion:
            messages.error(request, 'La dirección del centro es obligatoria.')
        elif not municipio:
            messages.error(request, 'El municipio o alcaldía es obligatorio.')
        elif not horarios_guardar:
            messages.error(request, 'Agrega al menos un horario de apertura y cierre.')
        else:
            # Crear perfil de centro en Supabase (vía PerfilFirebase)
            perfil = PerfilFirebase.objects.create(
                id=uuid.uuid4(),
                nombre=nombre_centro,
                correo=request.user.email,
                tipo_usuario='centro',
                eco_puntos_saldo=0,
                estado_cuenta=True
            )

            texto_descripcion = f"Responsable: {responsable}. {descripcion_publica or ''}"
            centro = Centro.objects.create(
                nombre_comercial=nombre_centro,
                descripcion=texto_descripcion,
                direccion_texto=direccion,
                telefono_contacto=telefono,
                correo_contacto=correo_publico or request.user.email,
                estado_operativo=False,
                validado=False,
                id_usuario=perfil
            )

            # Guardar horarios en Supabase
            try:
                for h in horarios_guardar:
                    horario_data = {
                        'id_centro': centro.id,
                        'dia_semana': h['dia_semana'],
                        'hora_apertura': h['apertura'],
                        'hora_cierre': h['cierre']
                    }
                    saff = supa.client.table('centros_horarios').insert(horario_data).execute()
            except Exception:
                pass

            # Guardar materiales (si existe la tabla)
            try:
                for mid in materiales_selectos:
                    # Insertar en centros_materiales para compatibilidad con sistema web
                    supa.client.table('centros_materiales').insert({'id_centro': centro.id, 'id_material': mid}).execute()
                    # Insertar también en precios_centro para compatibilidad con app Flutter
                    supa.client.table('precios_centro').insert({
                        'id_centro': centro.id,
                        'id_material': mid,
                        'precio_compra_actual': 0.0,
                    }).execute()
            except Exception:
                pass

            # Almacenar imagen
            try:
                if request.FILES.get('foto'):
                    bucket = 'centros'
                    foto_url = supa.upload_image(bucket=bucket, user_id=str(request.user.id), file=request.FILES['foto'], folder='', custom_filename=f'centro_{request.user.id}_{uuid.uuid4().hex}.jpg')
                    if foto_url:
                        centro.url_foto_portada = foto_url
                        centro.save()
            except Exception:
                pass

            messages.success(request, 'Solicitud enviada. Un administrador la revisará pronto.')
            return render(request, 'centro_pendiente.html', {'centro': centro})

    return render(request, 'completar_centro.html', {
        'responsable': responsable,
        'nombre_centro': nombre_centro,
        'telefono': telefono,
        'direccion': direccion,
        'municipio': municipio,
        'horarios': horarios,
        'codigo_postal': codigo_postal,
        'estado': estado,
        'localidad': localidad,
        'colonia': colonia,
        'descripcion_publica': descripcion_publica,
        'correo_publico': correo_publico,
        'materiales': materiales,
        'dias_semana': dias_semana,
        'materiales_seleccionados': materiales_seleccionados if request.method == 'POST' else [],
    })


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('home')
def centro_publico(request, centro_id):
    """
    Vista pública para mostrar los detalles de un centro específico
    """
    supa = SupabaseClient()
    
    # ========================================
    # 1. OBTENER DATOS DEL CENTRO
    # ========================================
    centro_data = None
    horarios_centro = []
    
    try:
        headers = {
            'apikey': supa.key,
            'Authorization': f'Bearer {supa.key}'
        }
        
        # Obtener datos del centro por ID
        url_centro = f"{supa.url}/rest/v1/centros_acopio?id=eq.{quote_plus(str(centro_id))}"
        response_centro = requests.get(url_centro, headers=headers)
        
        if response_centro.status_code == 200:
            centros = response_centro.json()
            if centros and len(centros) > 0:
                centro_data = centros[0]
                
                # Obtener horarios del centro
                url_horarios = f"{supa.url}/rest/v1/centros_horarios?id_centro=eq.{quote_plus(str(centro_id))}&order=dia_semana.asc"
                response_horarios = requests.get(url_horarios, headers=headers)
                if response_horarios.status_code == 200:
                    raw_horarios = response_horarios.json()
                    horarios_normalizados = []
                    if isinstance(raw_horarios, list):
                        for h in raw_horarios:
                            if not isinstance(h, dict):
                                continue
                            dia = h.get('dia_semana') or h.get('dia') or h.get('nombre_dia') or h.get('weekday') or 'Día'
                            apertura = h.get('apertura') or h.get('hora_inicio') or h.get('hora_apertura') or '--:--'
                            cierre = h.get('cierre') or h.get('hora_fin') or h.get('hora_cierre') or '--:--'
                            horarios_normalizados.append({
                                'dia': dia,
                                'apertura': apertura,
                                'cierre': cierre,
                            })
                    horarios_centro = horarios_normalizados
    except Exception:
        pass
    
    if not centro_data:
        # Si no existe el centro, mostrar 404
        from django.http import Http404
        raise Http404("Centro no encontrado")
    
    # ========================================
    # 2. PREPARAR CONTEXTO
    # ========================================
    horarios_texto = None
    if isinstance(centro_data, dict):
        horarios_texto = centro_data.get('horarios') or centro_data.get('horario') or centro_data.get('horario_texto')
    context = {
        'centro': centro_data,
        'horarios': horarios_centro,
        'horarios_texto': horarios_texto,
    }
    
    return render(request, 'centro_publico.html', context)



