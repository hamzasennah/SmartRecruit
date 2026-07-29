from __future__ import annotations

from types import SimpleNamespace

from scripts import free_port


def test_free_port_skips_unallowed_process(monkeypatch, capsys) -> None:
    process = SimpleNamespace(pid=123, name=lambda: "postgres.exe")
    connection = SimpleNamespace(
        laddr=SimpleNamespace(port=5432),
        status=free_port.psutil.CONN_LISTEN,
        pid=123,
    )
    monkeypatch.setattr(free_port.psutil, "net_connections", lambda kind: [connection])
    monkeypatch.setattr(free_port.psutil, "Process", lambda pid: process)

    free_port.free_port(5432, allowed_names={"uvicorn"}, assume_yes=True)

    output = capsys.readouterr().out
    assert "Processus non autorise" in output

# Role dans le projet:
# Ce fichier contient les tests unitaires pour free port. Il protege le comportement existant pendant les refactors sans appeler les services externes.
