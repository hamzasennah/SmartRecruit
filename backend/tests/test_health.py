from app.main import app
from fastapi.testclient import TestClient


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# Role dans le projet:
# Ce fichier verifie la route de sante. Il confirme que l'API expose les informations minimales attendues.
