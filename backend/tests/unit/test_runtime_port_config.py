"""Tests for backend runtime port configuration."""

from app.config import Settings


class TestRuntimePortConfig:
    def test_settings_prefers_backend_port_over_port(self, monkeypatch):
        monkeypatch.setenv("BACKEND_PORT", "9101")
        monkeypatch.setenv("PORT", "9102")

        settings = Settings(_env_file=None)

        assert settings.port == 9101

    def test_settings_uses_port_when_backend_port_is_missing(self, monkeypatch):
        monkeypatch.delenv("BACKEND_PORT", raising=False)
        monkeypatch.setenv("PORT", "9202")

        settings = Settings(_env_file=None)

        assert settings.port == 9202

    def test_settings_defaults_to_8001_when_no_port_env_exists(self, monkeypatch):
        monkeypatch.delenv("BACKEND_PORT", raising=False)
        monkeypatch.delenv("PORT", raising=False)

        settings = Settings(_env_file=None)

        assert settings.port == 8001
