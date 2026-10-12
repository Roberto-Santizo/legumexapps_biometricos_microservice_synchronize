"""
Configuracion del servicio, leida de variables de entorno.

En Laravel Cloud se definen en Environment > Variables; en local, en el
archivo .env (ver .env.example).
"""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from dotenv import load_dotenv
    # Ruta explicita: sin ella python-dotenv sube de carpeta y podria
    # leer el .env de APPS-BIO si este repo vive dentro de esa carpeta.
    load_dotenv(os.path.join(RAIZ, ".env"))
except ImportError:
    pass


def _env(clave, valor_por_defecto=None):
    valor = os.environ.get(clave)
    return valor if valor not in (None, "") else valor_por_defecto


def _env_int(clave, valor_por_defecto):
    try:
        return int(_env(clave, valor_por_defecto))
    except (TypeError, ValueError):
        return valor_por_defecto


def _env_bool(clave, valor_por_defecto=False):
    valor = _env(clave)
    if valor is None:
        return valor_por_defecto
    return valor.strip().lower() in ("true", "1", "si", "sí", "yes")


# --- ZKBio CVAccess (mismos nombres que en APPS-BIO) ---
ZKBIO_URL = (_env("ZKBIO_URL", "") or "").rstrip("/")
ZKBIO_API_USER = _env("ZKBIO_API_USER", "admin")
ZKBIO_API_PASSWORD_HASH = _env("ZKBIO_API_PASSWORD_HASH")
ZKBIO_BROWSER_TOKEN = _env("ZKBIO_BROWSER_TOKEN")

# ZKBio usa certificado autofirmado. Si ZKBIO_CERTIFICADO apunta a un .pem
# (ruta relativa a la raiz del repo), se valida contra el; si no, se usa
# ZKBIO_VERIFICAR_SSL (false por defecto, igual que app.py).
_CERTIFICADO = _env("ZKBIO_CERTIFICADO")
ZKBIO_VERIFY = (
    os.path.join(RAIZ, _CERTIFICADO)
    if _CERTIFICADO
    else _env_bool("ZKBIO_VERIFICAR_SSL", False)
)

ZKBIO_TIMEOUT = _env_int("ZKBIO_TIMEOUT", 20)
# Segundos que se reutiliza una sesion antes de renovarla por las buenas.
ZKBIO_VIGENCIA_SESION = _env_int("ZKBIO_VIGENCIA_SESION", 15 * 60)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# --- Sincronizador ---
# Esperas (segundos) entre reintentos de una misma persona; su largo
# define el maximo de intentos (len + 1).
ESPERAS_REINTENTO = [5, 15]
# Cuantos resultados recientes muestra GET /api/estado.
RESULTADOS_RECIENTES = _env_int("SYNC_RESULTADOS_RECIENTES", 100)


def faltantes_zkbio():
    """Nombres de las variables de ZKBio obligatorias que no estan definidas."""
    requeridas = {
        "ZKBIO_URL": ZKBIO_URL,
        "ZKBIO_API_PASSWORD_HASH": ZKBIO_API_PASSWORD_HASH,
        "ZKBIO_BROWSER_TOKEN": ZKBIO_BROWSER_TOKEN,
    }
    return [clave for clave, valor in requeridas.items() if not valor]
