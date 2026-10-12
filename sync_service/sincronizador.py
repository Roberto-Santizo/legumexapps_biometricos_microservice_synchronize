"""
Cola en memoria + hilo que dispara la sincronizacion de cada persona.

Igual que trigger_device_sync_batch_async en app.py: un solo hilo procesa
de a una persona, con una sola sesion de ZKBio. La cola vive en memoria,
asi que lo pendiente se pierde si el proceso se reinicia (APPS-BIO, si no
logra encolar, sincroniza directo).

Requiere UN solo proceso (gunicorn --workers 1): cada proceso tendria su
propia cola y su propia sesion de ZKBio.
"""

import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone

from . import config
from .zkbio import ClienteZkbio

log = logging.getLogger("sincronizador")


class Sincronizador:
    def __init__(self, cliente=None, esperas=None):
        self.cliente = cliente or ClienteZkbio()
        self.esperas = config.ESPERAS_REINTENTO if esperas is None else esperas
        self.cola = queue.Queue()
        self.resultados = deque(maxlen=config.RESULTADOS_RECIENTES)
        self.en_curso = None
        self.ultimo_error = None
        self._hilo = None
        self._lock = threading.Lock()

    def iniciar(self):
        with self._lock:
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(
                    target=self._bucle, name="zkbio-sync", daemon=True
                )
                self._hilo.start()

    def encolar(self, person_ids):
        for person_id in person_ids:
            self.cola.put(str(person_id))
        self.iniciar()

    def estado(self):
        return {
            "pendientes": self.cola.qsize(),
            "en_curso": self.en_curso,
            "ultimo_error": self.ultimo_error,
            "resultados_recientes": list(reversed(self.resultados)),
        }

    def procesar(self, person_id):
        """Sincroniza una persona con reintentos. Devuelve True si salio bien."""
        intentos = len(self.esperas) + 1
        for intento in range(1, intentos + 1):
            try:
                self.cliente.disparar_sincronizacion(person_id)
                self._registrar(person_id, "ok", intento)
                self.ultimo_error = None
                log.info("%s: sincronización disparada (intento %s)", person_id, intento)
                return True
            except Exception as e:  # ZkbioError o errores de red de requests
                detalle = str(e) or e.__class__.__name__
                self.ultimo_error = detalle
                log.warning("%s: intento %s/%s fallido: %s",
                            person_id, intento, intentos, detalle)
                if intento < intentos:
                    time.sleep(self.esperas[intento - 1])
                else:
                    self._registrar(person_id, "error", intento, detalle)
        return False

    def _registrar(self, person_id, estado, intentos, detalle=None):
        self.resultados.append({
            "person_id": person_id,
            "estado": estado,
            "intentos": intentos,
            "detalle": detalle,
            "momento": datetime.now(timezone.utc).isoformat(),
        })

    def _bucle(self):
        while True:
            person_id = self.cola.get()
            self.en_curso = person_id
            try:
                self.procesar(person_id)
            finally:
                self.en_curso = None
                self.cola.task_done()
