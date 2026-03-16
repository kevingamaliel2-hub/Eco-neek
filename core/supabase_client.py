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
        self.headers = {
            'apikey': self.key,
            'Authorization': f'Bearer {self.key}',
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
    
    def upload_image(self, bucket: str, user_id: str, file, folder: str = "avatars", custom_filename=None):
        """
        Sube una imagen a Supabase Storage
        
        Args:
            bucket: Nombre del bucket ('avatars' o 'centros')
            user_id: ID del usuario para organizar carpetas
            file: El archivo de imagen (request.FILES['campo'])
            folder: Subcarpeta (avatars, centros, etc)
            custom_filename: Nombre personalizado (opcional)
        
        Returns:
            str: URL pública de la imagen o None si hay error
        """
        try:
            # Leer el archivo
            file_content = file.read()
            file_ext = file.name.split('.')[-1].lower()
            
            # Validar extensiones permitidas
            if file_ext not in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                logger.warning("Extensión no permitida: %s", file_ext)
                return None
            
            # Generar nombre único o usar el personalizado
            import uuid
            if custom_filename:
                file_name = f"{folder}/{custom_filename}"
            else:
                unique_id = uuid.uuid4()
                file_name = f"{folder}/{user_id}_{unique_id}.{file_ext}"
            
            # Asegurar nombre de bucket correcto
                
            # URL de Supabase Storage
            url = f"{self.url}/storage/v1/object/{bucket}/{file_name}"
            
            # Headers
            headers = {
                'apikey': self.key,
                'Authorization': f'Bearer {self.key}',
                'Content-Type': file.content_type or f'image/{file_ext}',
            }
            
            # Subir archivo
            import requests
            response = requests.post(url, headers=headers, data=file_content)
            
            if response.status_code in [200, 201]:
                # Obtener URL pública
                public_url = f"{self.url}/storage/v1/object/public/{bucket}/{file_name}"
                return public_url
            else:
                logger.warning("Error subiendo imagen: %s", response.text)
                return None
                
        except Exception as e:
            logger.warning("Exception en upload_image: %s", e)
            return None
    
    def delete_image(self, bucket: str, file_path: str):
        """
        Elimina una imagen de Storage
        """
        try:
            url = f"{self.url}/storage/v1/object/{bucket}/{file_path}"
            headers = {
                'apikey': self.key,
                'Authorization': f'Bearer {self.key}',
            }
            import requests
            response = requests.delete(url, headers=headers)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.warning("Error eliminando imagen: %s", e)
            return False