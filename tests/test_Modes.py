from dataclasses import replace
from bs4 import BeautifulSoup
import src.main as m
from src.db import Database


class TestModes:

    @staticmethod
    def _items(name, cls):
        with open("./tests/html/{}.html".format(name)) as f:
            return cls.parse_tag(BeautifulSoup(f.read(), "html.parser"))


    def test_archive_mode_skips_webhook_and_persists(self, monkeypatch):
        monkeypatch.setattr(m.config, "mode", "archive")
        monkeypatch.setattr(m.config, "webhook_urls", [])
        sends = []
        monkeypatch.setattr(m.DiscordWebhook, "send", lambda self: sends.append(self.data.edge_no))

        db = Database(":memory:")
        items = self._items("dividends", m.Dividend)
        m._diff_and_send("dividends", items, db)
        new_item = replace(items[0], edge_no="zz_archive", circular_number="C")
        m._diff_and_send("dividends", items + [new_item], db)

        assert sends == []
        assert "zz_archive" in db.get_existing_edge_nos("dividends", ["zz_archive"])
        db.close()


    def test_both_mode_sends_and_persists(self, monkeypatch):
        monkeypatch.setattr(m.config, "mode", "both")
        monkeypatch.setattr(m.config, "webhook_urls", ["https://discord.com/api/webhooks/x"])
        sends = []
        monkeypatch.setattr(m.DiscordWebhook, "send", lambda self: sends.append(self.data.edge_no))

        db = Database(":memory:")
        items = self._items("rights", m.StockRights)
        m._diff_and_send("rights", items, db)
        new_item = replace(items[0], edge_no="yy_both", circular_number="C")
        m._diff_and_send("rights", items + [new_item], db)

        assert sends == ["yy_both"]
        assert "yy_both" in db.get_existing_edge_nos("stock_rights", ["yy_both"])
        db.close()


    def test_webhook_mode_uses_mem_cache(self, monkeypatch):
        monkeypatch.setattr(m.config, "mode", "webhook")
        monkeypatch.setattr(m.config, "webhook_urls", ["https://discord.com/api/webhooks/x"])
        sends = []
        monkeypatch.setattr(m.DiscordWebhook, "send", lambda self: sends.append(self.data.edge_no))

        cache = {}
        items = self._items("dividends", m.Dividend)
        m._diff_and_send_mem("dividends", items, cache)
        assert sends == []
        new_item = replace(items[0], edge_no="xx_webhook", circular_number="C")
        m._diff_and_send_mem("dividends", items + [new_item], cache)
        assert sends == ["xx_webhook"]


    def test_multiple_webhooks_all_send(self, monkeypatch):
        monkeypatch.setattr(m.config, "mode", "both")
        monkeypatch.setattr(m.config, "webhook_urls", [
            "https://discord.com/api/webhooks/a",
            "https://discord.com/api/webhooks/b",
        ])
        sends = []
        monkeypatch.setattr(m.DiscordWebhook, "send", lambda self: sends.append(self.url))

        db = Database(":memory:")
        items = self._items("rights", m.StockRights)
        m._diff_and_send("rights", items, db)
        new_item = replace(items[0], edge_no="mm_multi", circular_number="C")
        m._diff_and_send("rights", items + [new_item], db)

        assert sends == [
            "https://discord.com/api/webhooks/a",
            "https://discord.com/api/webhooks/b",
        ]
        db.close()
