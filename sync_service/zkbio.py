"""
Cliente minimo de ZKBio CVAccess: login de 3 pasos y el "truco" de
sincronizacion.

Portado de app.py (sign_in_method, _zkbio_parece_pagina_login,
trigger_device_sync). Solo lo usa el worker, que es un unico proceso que
atiende la cola de a una persona por vez, asi que la sesion no necesita
lock.
"""

import time

import requests
import urllib3

from . import config

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ACCEPT_HTML = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,"
    "image/avif,image/webp,image/apng,*/*;q=0.8"
)


class ZkbioError(Exception):
    """Fallo al autenticarse o al disparar la sincronizacion."""


def parece_pagina_login(response):
    """
    True si la respuesta es en realidad el formulario de login.

    ZKBio no responde 401/403 con la sesion vencida: devuelve HTTP 200 con
    el HTML del login (o redirige a el).
    """
    body = (response.text or "").lower()
    final_url = (response.url or "").lower()

    if ("login.do" in final_url or "biologin.do" in final_url) and response.history:
        return True

    marcadores = (
        "<title>login",
        'id="loginpage"',
        'name="username"',
        'name="password"',
        "login-form",
    )
    return "<html" in body and any(m in body for m in marcadores)


class ClienteZkbio:
    def __init__(self, base_url=None, usuario=None, password_hash=None,
                 browser_token=None, verify=None, timeout=None, vigencia=None):
        self.base_url = (base_url or config.ZKBIO_URL).rstrip("/")
        self.usuario = usuario or config.ZKBIO_API_USER
        self.password_hash = password_hash or config.ZKBIO_API_PASSWORD_HASH
        self.browser_token = browser_token or config.ZKBIO_BROWSER_TOKEN
        self.verify = config.ZKBIO_VERIFY if verify is None else verify
        self.timeout = timeout or config.ZKBIO_TIMEOUT
        self.vigencia = vigencia or config.ZKBIO_VIGENCIA_SESION
        self.sesion = requests.Session()
        self.ultimo_login = 0.0

    # ------------------------------------------------------------------
    # Sesion
    # ------------------------------------------------------------------
    def iniciar_sesion(self):
        """
        Flujo de 3 pasos (ver sign_in_method en app.py):
            1. GET bioLogin.do con Browser-Token -> cookie previa.
            2. POST login.do con credenciales + browserToken (cuerpo y header).
            3. GET main.do?home: si devuelve el login, la sesion NO sirve.
        """
        self.sesion.cookies.clear()
        bio_login_url = f"{self.base_url}/bioLogin.do"

        r = self.sesion.get(
            bio_login_url,
            headers={
                "User-Agent": config.USER_AGENT,
                "Browser-Token": self.browser_token,
                "Accept": ACCEPT_HTML,
            },
            verify=self.verify, timeout=self.timeout,
        )
        if not r.ok:
            raise ZkbioError(f"bioLogin.do devolvió HTTP {r.status_code}")

        r = self.sesion.post(
            f"{self.base_url}/login.do",
            data={
                "username": self.usuario,
                "password": self.password_hash,
                "checkCode": "",
                "browserToken": self.browser_token,
            },
            headers={
                "User-Agent": config.USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
                "Referer": bio_login_url,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Browser-Token": self.browser_token,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            },
            verify=self.verify, timeout=self.timeout,
        )
        if not r.ok:
            raise ZkbioError(f"login.do devolvió HTTP {r.status_code}")
        if "SESSION" not in self.sesion.cookies.get_dict():
            raise ZkbioError(
                "login.do no entregó la cookie SESSION "
                f"(cookies: {list(self.sesion.cookies.get_dict())})"
            )

        r = self.sesion.get(
            f"{self.base_url}/main.do?home",
            headers={
                "User-Agent": config.USER_AGENT,
                "Browser-Token": self.browser_token,
                "Referer": bio_login_url,
                "Accept": ACCEPT_HTML,
            },
            verify=self.verify, timeout=self.timeout,
        )
        if not r.ok:
            raise ZkbioError(f"main.do?home devolvió HTTP {r.status_code}")
        if parece_pagina_login(r):
            raise ZkbioError(
                "main.do?home devuelve el formulario de acceso: la sesión "
                "no quedó autenticada (revisar hash de contraseña y Browser-Token)"
            )

        self.ultimo_login = time.time()

    def asegurar_sesion(self, forzar=False):
        sin_cookie = "SESSION" not in self.sesion.cookies.get_dict()
        vencida = (time.time() - self.ultimo_login) > self.vigencia
        if forzar or sin_cookie or vencida:
            self.iniciar_sesion()

    # ------------------------------------------------------------------
    # Sincronizacion
    # ------------------------------------------------------------------
    def disparar_sincronizacion(self, person_id):
        """
        Visita accPerson.do?edit&personId=<id>. ZKBio encola los comandos
        pendientes de esa persona hacia los dispositivos como efecto
        secundario de renderizar esa pantalla (ver trigger_device_sync en
        app.py).

        Raises:
            ZkbioError: si no se pudo autenticar o ZKBio no respondio bien.
        """
        url = f"{self.base_url}/accPerson.do"
        params = {"edit": "", "personId": person_id}
        headers = {
            "User-Agent": config.USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{self.base_url}/",
        }

        self.asegurar_sesion()
        r = self.sesion.get(url, params=params, headers=headers,
                            verify=self.verify, timeout=self.timeout)

        # Sesion vencida entre peticiones: se renueva y se intenta una vez.
        if parece_pagina_login(r):
            self.asegurar_sesion(forzar=True)
            r = self.sesion.get(url, params=params, headers=headers,
                                verify=self.verify, timeout=self.timeout)

        if parece_pagina_login(r):
            raise ZkbioError("ZKBio devolvió el formulario de acceso")
        if not r.ok:
            raise ZkbioError(f"accPerson.do devolvió HTTP {r.status_code}")
