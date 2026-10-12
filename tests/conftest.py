import pytest

from sync_service import config

ZK = "https://zkbio.test:8098"


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setattr(config, "ZKBIO_URL", ZK)
    monkeypatch.setattr(config, "ZKBIO_API_PASSWORD_HASH", "hash")
    monkeypatch.setattr(config, "ZKBIO_BROWSER_TOKEN", "browser-token")
    monkeypatch.setattr(config, "ZKBIO_VERIFY", False)
