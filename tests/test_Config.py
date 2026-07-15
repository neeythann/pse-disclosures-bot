import pytest
from src.config import Config


@pytest.fixture(autouse=True)
def reset_singleton():
    Config._instance = None
    yield
    Config._instance = None


class TestConfig:

    def test_default_mode_is_both(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_URL", "https://x")
        monkeypatch.delenv("OUTPUT_MODE", raising=False)
        assert Config().mode == "both"


    def test_archive_mode_allows_no_webhook(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_URL", raising=False)
        monkeypatch.setenv("OUTPUT_MODE", "archive")
        c = Config()
        assert c.mode == "archive"
        assert c.webhook_urls == []


    def test_webhook_mode_requires_webhook_url(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_URL", raising=False)
        monkeypatch.setenv("OUTPUT_MODE", "webhook")
        with pytest.raises(ValueError):
            Config()


    def test_both_mode_requires_webhook(self, monkeypatch):
        monkeypatch.delenv("WEBHOOK_URL", raising=False)
        monkeypatch.setenv("OUTPUT_MODE", "both")
        with pytest.raises(ValueError):
            Config()


    def test_invalid_mode_raises(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_URL", "https://x")
        monkeypatch.setenv("OUTPUT_MODE", "bogus")
        with pytest.raises(ValueError):
            Config()


    def test_singleton_identity(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_URL", "https://x")
        assert Config() is Config()


    def test_comma_delimited_webhook_urls(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/a , https://discord.com/api/webhooks/b,")
        c = Config()
        assert c.webhook_urls == [
            "https://discord.com/api/webhooks/a",
            "https://discord.com/api/webhooks/b",
        ]


    def test_single_webhook_url(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_URL", "https://discord.com/api/webhooks/x")
        c = Config()
        assert c.webhook_urls == ["https://discord.com/api/webhooks/x"]
