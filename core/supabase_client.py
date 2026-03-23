import os
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

class SupabaseClient:
    """Lightweight Supabase client using REST calls via requests.

    This avoids the heavy `supabase` package so we can run without
    building native dependencies. Only the portions we need are implemented.
    """

    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip('/')
        self.key = settings.SUPABASE_ANON_KEY
        self.service_role_key = getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', None) or self.key
        if not getattr(settings, 'SUPABASE_SERVICE_ROLE_KEY', None):
            logger.warning('No SUPABASE_SERVICE_ROLE_KEY configurado. Storage puede fallar en bucket y escritura.')
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
            'Content-Type': 'application/json',
        }
        self.storage_headers = {
            'apikey': self.service_role_key,
            'Authorization': f'Bearer {self.service_role_key}',
            'Content-Type': 'application/json',
        }
        # Provide compatibility for old code that used `supa.client.table(...)`
        # by exposing a `client` property pointing to this instance.
        self.client = self

    # minimal query builder to mimic supabase-python interface
    class Table:
        def __init__(self, parent, name):
            self.parent = parent
            self.name = name
            self.method = 'GET'
            self.params = {}
            self.payload = None

        def select(self, fields='*', count=None):
            self.method = 'GET'
            if fields:
                self.params['select'] = fields
            if count:
                self.params['count'] = count
            return self

        def eq(self, column, value):
            # Supabase REST expects booleans as lowercase 'true'/'false'
            if isinstance(value, bool):
                val = 'true' if value else 'false'
            else:
                val = value
            self.params[column] = f'eq.{val}'
            return self

        def order(self, column, desc=False):
            self.params['order'] = f"{column}.{'desc' if desc else 'asc'}"
            return self

        def limit(self, amt):
            self.params['limit'] = str(amt)
            return self

        def insert(self, data):
            self.method = 'POST'
            self.payload = data
            return self

        def update(self, data):
            self.method = 'PATCH'
            self.payload = data
            return self

        def delete(self):
            self.method = 'DELETE'
            self.payload = None
            return self

        def single(self):
            # Add single() support for queries that return one result
            return self

        def execute(self):
            url = self.parent._table_url(self.name)
            return self.parent._request(self.method, url, params=self.params, json_body=self.payload)

    def table(self, name: str):
        return SupabaseClient.Table(self, name)

    # helpers
    def _table_url(self, table_name: str):
        return f"{self.url}/rest/v1/{table_name}"

    def _select(self, params: dict, fields: str):
        if fields:
            params['select'] = fields

    def _apply_eq(self, params: dict, column: str, value):
        params[column] = f'eq.{value}'

    def _apply_order(self, params: dict, column: str, desc: bool):
        params['order'] = f"{column}.{'desc' if desc else 'asc'}"

    def _apply_limit(self, params: dict, count: int):
        params['limit'] = str(count)

    def _request(self, method: str, url: str, params=None, json_body=None):
        try:
            resp = requests.request(method, url, headers=self.headers, params=params, json=json_body)
            class Resp: pass
            r = Resp()
            try:
                r.data = resp.json()
            except ValueError:
                r.data = None
            r.error = None if resp.ok else resp.text
            return r
        except Exception as e:
            logger.warning("HTTP error (%s %s): %s", method, url, e)
            class Resp: pass
            r = Resp()
            r.data = None
            r.error = str(e)
            return r

    # Auth functions
    def sign_in(self, email: str, password: str):
        try:
            url = f"{self.url}/auth/v1/token?grant_type=password"
            headers = {
                'apikey': self.key,
                'Authorization': f'Bearer {self.key}',
                'Content-Type': 'application/json',
            }
            payload = {
                'email': email,
                'password': password,
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except ValueError:
                    data = {'access_token': None, 'error': 'invalid json'}
                return type('R', (), {'data': data, 'error': None})
            else:
                try:
                    j = resp.json()
                    err = j.get('error_description') or j.get('error') or resp.text
                except Exception:
                    err = resp.text
                return type('R', (), {'data': None, 'error': err})
        except Exception as e:
            return type('R', (), {'data': None, 'error': str(e)})

    # QR functions
    def get_user_qr_url(self, user_id):
        return None

    def update_user_qr(self, user_id, qr_image_path):
        return None

    # Profile functions
    def crear_perfil(self, user_data):
        url = self._table_url('perfiles')
        resp = self._request('POST', url, json_body=user_data)
        if resp.error:
            logger.warning("Supabase error: %s", resp.error)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    def obtener_perfil(self, user_id):
        url = self._table_url('perfiles')
        params = {}
        self._select(params, '*')
        self._apply_eq(params, 'id', user_id)
        resp = self._request('GET', url, params=params)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    def actualizar_perfil(self, user_id, data):
        url = self._table_url('perfiles')
        params = {}
        self._apply_eq(params, 'id', user_id)
        resp = self._request('PATCH', url, params=params, json_body=data)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    # Center functions
    def crear_centro(self, centro_data):
        url = self._table_url('centros_acopio')
        resp = self._request('POST', url, json_body=centro_data)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    def obtener_centro_por_usuario(self, user_id):
        url = self._table_url('centros_acopio')
        params = {}
        self._select(params, '*')
        self._apply_eq(params, 'id_usuario', user_id)
        resp = self._request('GET', url, params=params)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    def actualizar_centro(self, centro_id, data):
        url = self._table_url('centros_acopio')
        params = {}
        self._apply_eq(params, 'id', centro_id)
        resp = self._request('PATCH', url, params=params, json_body=data)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    # Material functions
    def obtener_materiales(self):
        url = self._table_url('catalogo_materiales')
        params = {}
        self._select(params, '*')
        self._apply_order(params, 'nombre_material', desc=False)
        resp = self._request('GET', url, params=params)
        return resp.data if isinstance(resp.data, list) else []

    # Review functions
    def obtener_resenas_centro(self, centro_id):
        url = self._table_url('resenas')
        params = {}
        self._select(params, '*, perfiles(nombre, apellido)')
        self._apply_eq(params, 'id_centro', centro_id)
        self._apply_order(params, 'fecha', desc=True)
        self._apply_limit(params, 20)
        resp = self._request('GET', url, params=params)
        return resp.data if isinstance(resp.data, list) else []

    def calcular_promedio_resenas(self, centro_id):
        url = self._table_url('resenas')
        params = {}
        self._select(params, 'calificacion')
        self._apply_eq(params, 'id_centro', centro_id)
        resp = self._request('GET', url, params=params)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            calificaciones = [r['calificacion'] for r in resp.data if isinstance(r, dict) and 'calificacion' in r]
            promedio = sum(calificaciones) / len(calificaciones) if calificaciones else 0
            total = len(calificaciones)
            return round(promedio, 1), total
        return 0, 0

    # Reward / Canje / Suggestion functions
    def obtener_recompensas(self, solo_disponibles: bool = True):
        """Retorna lista de recompensas desde Supabase."""
        url = self._table_url('recompensas')
        params = {}
        self._select(params, '*')
        if solo_disponibles:
            self._apply_eq(params, 'disponible', True)
        resp = self._request('GET', url, params=params)
        return resp.data if isinstance(resp.data, list) else []

    # Auth helpers (use Supabase Auth REST endpoints)
    def sign_in(self, email: str, password: str):
        """Sign in a user via Supabase Auth (password grant). Returns parsed JSON or None."""
        try:
            url = f"{self.url}/auth/v1/token?grant_type=password"
            body = {'email': email, 'password': password}
            resp = requests.post(url, headers=self.headers, json=body)
            class Resp: pass
            r = Resp()
            try:
                r.data = resp.json()
            except ValueError:
                r.data = None
            r.error = None if resp.ok else resp.text
            return r
        except Exception as e:
            logger.warning('Supabase auth error: %s', e)
            class Resp: pass
            r = Resp()
            r.data = None
            r.error = str(e)
            return r

    def sign_up(self, email: str, password: str):
        """Sign up a new user in Supabase Auth and return user metadata."""
        try:
            url = f"{self.url}/auth/v1/signup"
            body = {'email': email, 'password': password}
            resp = requests.post(url, headers=self.headers, json=body)
            class Resp: pass
            r = Resp()
            try:
                r.data = resp.json()
            except ValueError:
                r.data = None
            r.error = None if resp.ok else resp.text
            return r
        except Exception as e:
            logger.warning('Supabase signup error: %s', e)
            class Resp: pass
            r = Resp()
            r.data = None
            r.error = str(e)
            return r

    def obtener_canjes_por_usuario(self, usuario_id):
        url = self._table_url('canjes')
        params = {}
        self._select(params, '*')
        self._apply_eq(params, 'id_usuario', usuario_id)
        self._apply_order(params, 'fecha_canje', desc=True)
        resp = self._request('GET', url, params=params)
        return resp.data if isinstance(resp.data, list) else []

    def insertar_sugerencia(self, usuario_id, tipo, mensaje):
        url = self._table_url('sugerencias')
        data = {'id_usuario': usuario_id, 'tipo': tipo, 'mensaje': mensaje}
        resp = self._request('POST', url, json_body=data)
        if isinstance(resp.data, list) and len(resp.data) > 0:
            return resp.data[0] if isinstance(resp.data[0], dict) else None
        return None

    # ============================================
    # NUEVOS MÉTODOS PARA SUBIR ARCHIVOS
    # ============================================
    
    def _normalize_path(self, folder: str, filename: str):
        folder = (folder or '').strip('/')
        filename = filename.strip('/')
        if folder:
            return f"{folder}/{filename}"
        return filename

    def _extract_bucket_object(self, public_url: str):
        # Esperamos url tipo: .../storage/v1/object/public/{bucket}/{object}
        try:
            if not public_url:
                return None, None
            parts = public_url.split('/storage/v1/object/public/')
            if len(parts) != 2:
                return None, None
            rest = parts[1]
            bucket, object_path = rest.split('/', 1)
            # Eliminar query string o fragmentos si los tiene
            object_path = object_path.split('?', 1)[0].split('#', 1)[0]
            return bucket, object_path
        except Exception:
            return None, None

    def create_bucket(self, bucket: str, public: bool = True):
        """Crea un bucket de Supabase Storage si no existe."""
        try:
            url = f"{self.url}/storage/v1/bucket"
            headers = {
                'apikey': self.service_role_key,
                'Authorization': f'Bearer {self.service_role_key}',
                'Content-Type': 'application/json',
            }
            payload = {'name': bucket, 'public': public}
            import requests
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code in [200, 201]:
                return True
            logger.warning("No se pudo crear bucket %s: %s %s", bucket, response.status_code, response.text)
            return False
        except Exception as e:
            logger.warning("Exception en create_bucket: %s", e)
            return False

    def upload_image(self, bucket: str, user_id: str, file, folder: str = "avatars", custom_filename=None, max_size_bytes: int = 2 * 1024 * 1024):
        """
        Sube una imagen a Supabase Storage. Crea el bucket si no existe.
        """
        try:
            file_content = file.read()
            original_size = len(file_content)
            file_ext = file.name.split('.')[-1].lower()

            if max_size_bytes and original_size > max_size_bytes:
                logger.warning("Archivo demasiado grande para upload_image: %s bytes (límite %s). Intentando compresión.", original_size, max_size_bytes)
                try:
                    from PIL import Image
                    from io import BytesIO

                    img = Image.open(BytesIO(file_content))
                    if img.mode in ('RGBA', 'LA'):
                        fondo = Image.new('RGB', img.size, (255, 255, 255))
                        fondo.paste(img, mask=img.split()[-1])
                        img = fondo
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')

                    comprimido = None
                    for quality in [85, 75, 65, 55, 45, 35, 25]:
                        buffer = BytesIO()
                        img.save(buffer, format='JPEG', quality=quality, optimize=True)
                        candidate = buffer.getvalue()
                        if len(candidate) <= max_size_bytes:
                            comprimido = candidate
                            file_ext = 'jpg'
                            break

                    if comprimido is not None:
                        file_content = comprimido
                        logger.info('Imagen comprimida a %s bytes con calidad %s para cumplir el límite.', len(file_content), quality)
                    else:
                        logger.warning('No se pudo comprimir la imagen por debajo de %s bytes.', max_size_bytes)
                        return None
                except ImportError:
                    logger.warning('Pillow (PIL) no está instalado, no se puede comprimir la imagen. Ajuste max_size_bytes o instale Pillow.')
                    return None
                except Exception as e:
                    logger.warning('Error al intentar comprimir imagen: %s', e)
                    return None

            if max_size_bytes and len(file_content) > max_size_bytes:
                logger.warning("Archivo sigue siendo demasiado grande después de compresión: %s bytes (límite %s)", len(file_content), max_size_bytes)
                return None

            if file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'webm']:
                logger.warning("Extensión no permitida: %s", file_ext)
                return None

            import uuid
            if custom_filename:
                filename = custom_filename
            else:
                filename = f"{user_id}_{uuid.uuid4().hex}.{file_ext}"

            file_name = self._normalize_path(folder, filename)
            url = f"{self.url}/storage/v1/object/{bucket}/{file_name}"

            headers = {
                'apikey': self.service_role_key,
                'Authorization': f'Bearer {self.service_role_key}',
                'Content-Type': file.content_type or f'image/{file_ext}',
            }
            import requests
            response = requests.post(url, headers=headers, data=file_content)

            if response.status_code in [200, 201]:
                return f"{self.url}/storage/v1/object/public/{bucket}/{file_name}"

            # Si el bucket no existe, intentar crearlo y reintentar una vez
            if response.status_code in [403, 404] or 'bucket' in (response.text or '').lower():
                logger.warning("Bucket ausente o acceso denegado al subir %s: %s", bucket, response.text)
                if self.create_bucket(bucket):
                    response2 = requests.post(url, headers=headers, data=file_content)
                    if response2.status_code in [200, 201]:
                        return f"{self.url}/storage/v1/object/public/{bucket}/{file_name}"
                    logger.warning("Reintento de upload falló (%s): %s", response2.status_code, response2.text)
            logger.warning("Error subiendo imagen (%s): %s", response.status_code, response.text)
            return None
        except Exception as e:
            logger.warning("Exception en upload_image: %s", e)
            return None

    def delete_image(self, bucket: str, file_path: str):
        try:
            file_path = file_path.strip('/')
            url = f"{self.url}/storage/v1/object/{bucket}/{file_path}"
            headers = {
                'apikey': self.service_role_key,
                'Authorization': f'Bearer {self.service_role_key}',
            }
            import requests
            response = requests.delete(url, headers=headers)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.warning("Error eliminando imagen: %s", e)
            return False

    def delete_image_by_public_url(self, public_url: str):
        bucket, object_path = self._extract_bucket_object(public_url)
        if bucket and object_path:
            return self.delete_image(bucket, object_path)
        return False