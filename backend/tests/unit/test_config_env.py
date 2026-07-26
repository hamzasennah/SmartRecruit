import os

from app.config import load_backend_env


def test_load_backend_env_accepts_utf8_bom(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("\ufeffNVIDIA_API_KEY=test-key\n", encoding="utf-8")
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)

    load_backend_env(env_file)

    assert os.getenv("NVIDIA_API_KEY") == "test-key"
