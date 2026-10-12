from unittest.mock import MagicMock

import responses
from responses import matchers

from sync_service.sincronizador import Sincronizador
from sync_service.web import create_app
from sync_service.zkbio import ClienteZkbio

from conftest import ZK

PAGINA_LOGIN = '<html><head><title>Login</title></head><body><input name="username"></body></html>'


def _registrar_login(rsps):
    rsps.get(f"{ZK}/bioLogin.do", body="<html>pre</html>")
    rsps.post(f"{ZK}/login.do", json={"ret": "ok"},
              headers={"Set-Cookie": "SESSION=abc123; Path=/"})
    rsps.get(f"{ZK}/main.do?home", body="<html>inicio</html>")


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------
def test_post_sync_encola_sin_token():
    sincronizador = MagicMock()
    cliente = create_app(sincronizador).test_client()

    r = cliente.post("/api/sync", json={"person_ids": ["p1", "p2"]})

    assert r.status_code == 202
    assert r.get_json() == {"encolados": 2}
    sincronizador.encolar.assert_called_once_with(["p1", "p2"])


def test_post_sync_acepta_un_solo_id():
    sincronizador = MagicMock()
    create_app(sincronizador).test_client().post("/api/sync", json={"person_ids": "p1"})
    sincronizador.encolar.assert_called_once_with(["p1"])


def test_estado():
    sincronizador = Sincronizador(cliente=MagicMock(), esperas=[])
    r = create_app(sincronizador).test_client().get("/api/estado")
    assert r.status_code == 200
    assert r.get_json()["pendientes"] == 0


# ----------------------------------------------------------------------
# Sincronizador + cliente ZKBio
# ----------------------------------------------------------------------
@responses.activate
def test_sincroniza_persona():
    _registrar_login(responses)
    responses.get(f"{ZK}/accPerson.do", body="<html>acceso</html>",
                  match=[matchers.query_string_matcher("edit=&personId=p1")])
    s = Sincronizador(cliente=ClienteZkbio(), esperas=[])

    assert s.procesar("p1") is True
    assert s.estado()["resultados_recientes"][0]["estado"] == "ok"
    assert responses.calls[0].request.headers["Browser-Token"] == "browser-token"


@responses.activate
def test_renueva_sesion_si_zkbio_devuelve_login():
    _registrar_login(responses)
    responses.get(f"{ZK}/accPerson.do", body=PAGINA_LOGIN)
    _registrar_login(responses)
    responses.get(f"{ZK}/accPerson.do", body="<html>acceso</html>")
    s = Sincronizador(cliente=ClienteZkbio(), esperas=[])

    assert s.procesar("p1") is True
    logins = [c for c in responses.calls if c.request.url.endswith("/login.do")]
    assert len(logins) == 2


@responses.activate
def test_reintenta_y_registra_error():
    _registrar_login(responses)
    responses.get(f"{ZK}/accPerson.do", status=500)
    s = Sincronizador(cliente=ClienteZkbio(), esperas=[0])

    assert s.procesar("p1") is False
    resultado = s.estado()["resultados_recientes"][0]
    assert resultado["estado"] == "error"
    assert resultado["intentos"] == 2
    assert "HTTP 500" in resultado["detalle"]


def test_hilo_procesa_la_cola():
    cliente = MagicMock()
    s = Sincronizador(cliente=cliente, esperas=[])

    s.encolar(["p1", "p2"])
    s.cola.join()

    assert [c.args[0] for c in cliente.disparar_sincronizacion.call_args_list] == ["p1", "p2"]
