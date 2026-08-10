from types import SimpleNamespace

import hashlib
import hmac
import json

from bs4 import BeautifulSoup

from src.main import (
    CompanyDisclosure,
    GenericWebhook,
    _build_headers,
    _fetch_disclosure_links,
    _parse_viewer_links,
    create_webhook,
)


class TestViewerParse:

    @staticmethod
    def _soup() -> BeautifulSoup:
        with open("./tests/html/viewer.html") as f:
            return BeautifulSoup(f.read(), 'html.parser')

    def test_parse_viewer_links(self):
        links = _parse_viewer_links(TestViewerParse._soup())
        assert links == {
            "main_doc_url": "https://edge.pse.com.ph/downloadHtml.do?file_id=1825618",
            "attachment_links": [
                {
                    "name": "Oct 16, 2025 AmendedDIS.pdf",
                    "url": "https://edge.pse.com.ph/downloadFile.do?file_id=1825619",
                }
            ],
        }

    def test_parse_viewer_links_no_attachments(self, monkeypatch):
        class EmptySoup:
            def find(self, name, id=None):
                if name == "iframe":
                    return None
                if name == "select":
                    return None
                return None
        assert _parse_viewer_links(EmptySoup()) == {
            "main_doc_url": "",
            "attachment_links": [],
        }


class TestGenericWebhook:

    @staticmethod
    def _item() -> CompanyDisclosure:
        return CompanyDisclosure(
            _id="/companyInformation/form.do?cmpy_id=97",
            company_name="Philcomsat Holdings Corporation",
            title="[Amend-1]Information Statement",
            edge_no="024cf69f83de72b2ec6e1601ccee8f59",
            form_type="17-5",
            date="Oct 16, 2025 05:41 PM",
            circular_number="CR07418-2025",
        )

    def test_format_data(self, monkeypatch):
        monkeypatch.setattr(
            "src.main._fetch_disclosure_links",
            lambda edge_no: {
                "main_doc_url": "https://edge.pse.com.ph/downloadHtml.do?file_id=1825618",
                "attachment_links": [
                    {"name": "AmendedDIS.pdf", "url": "https://edge.pse.com.ph/downloadFile.do?file_id=1825619"}
                ],
            },
        )
        payload = GenericWebhook("https://listener.example.com/hook", TestGenericWebhook._item())._format_data()
        assert payload == {
            "type": "CompanyDisclosure",
            "object": {
                "_id": "/companyInformation/form.do?cmpy_id=97",
                "company_name": "Philcomsat Holdings Corporation",
                "title": "[Amend-1]Information Statement",
                "edge_no": "024cf69f83de72b2ec6e1601ccee8f59",
                "form_type": "17-5",
                "date": "Oct 16, 2025 05:41 PM",
                "circular_number": "CR07418-2025",
            },
            "viewer_url": "https://edge.pse.com.ph/openDiscViewer.do?edge_no=024cf69f83de72b2ec6e1601ccee8f59",
            "main_doc_url": "https://edge.pse.com.ph/downloadHtml.do?file_id=1825618",
            "attachment_links": [
                {"name": "AmendedDIS.pdf", "url": "https://edge.pse.com.ph/downloadFile.do?file_id=1825619"}
            ],
        }


class TestCreateWebhook:
    def test_unknown_host_falls_back_to_generic(self):
        hook = create_webhook("https://listener.example.com/hook", SimpleNamespace())
        assert isinstance(hook, GenericWebhook)

    def test_discord_host(self):
        assert type(create_webhook("https://discord.com/api/webhooks/x", SimpleNamespace())).__name__ == "DiscordWebhook"

    def test_slack_host(self):
        assert type(create_webhook("https://hooks.slack.com/services/x", SimpleNamespace())).__name__ == "SlackWebhook"


class TestFetchDisclosureLinks:
    def test_fetch(self, monkeypatch):
        calls = []
        with open("./tests/html/viewer.html") as f:
            body = f.read()

        class FakeResponse:
            status_code = 200
            content = body.encode()

        def fake_get(url, headers):
            calls.append(url)
            return FakeResponse()

        monkeypatch.setattr("src.main.requests.get", fake_get)
        monkeypatch.setattr("src.main._disclosure_links_cache", {})
        links = _fetch_disclosure_links("024cf69f83de72b2ec6e1601ccee8f59")
        assert calls == ["https://edge.pse.com.ph/openDiscViewer.do?edge_no=024cf69f83de72b2ec6e1601ccee8f59"]
        assert links["main_doc_url"] == "https://edge.pse.com.ph/downloadHtml.do?file_id=1825618"
        assert links["attachment_links"][0]["url"] == "https://edge.pse.com.ph/downloadFile.do?file_id=1825619"

    def test_fetch_non_200(self, monkeypatch):
        class FakeResponse:
            status_code = 500
            content = b""

        def fake_get(url, headers):
            return FakeResponse()

        monkeypatch.setattr("src.main.requests.get", fake_get)
        monkeypatch.setattr("src.main._disclosure_links_cache", {})
        assert _fetch_disclosure_links("bad") is None


class TestHmacHeaders:

    @staticmethod
    def _expected(timestamp: str, secret: str, body: bytes) -> str:
        message = "{}.".format(timestamp).encode() + body
        return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

    def test_no_secret_adds_no_signature(self, monkeypatch):
        monkeypatch.setattr("src.main.config.hmac_secret", None)
        assert _build_headers(b'{"a":1}') == {"Content-Type": "application/json"}

    def test_secret_adds_signature_and_timestamp_headers(self, monkeypatch):
        monkeypatch.setattr("src.main.config.hmac_secret", "s3cret")
        monkeypatch.setattr("src.main.time", lambda: 1700000000)
        body = b'{"a":1}'
        headers = _build_headers(body)
        assert headers["X-Webhook-Timestamp"] == "1700000000"
        assert headers["X-Webhook-Signature-V2"] == self._expected("1700000000", "s3cret", body)

    def test_custom_header_names_from_config(self, monkeypatch):
        monkeypatch.setattr("src.main.config.hmac_secret", "s3cret")
        monkeypatch.setattr("src.main.config.signature_header", "X-Custom-Sig")
        monkeypatch.setattr("src.main.config.timestamp_header", "X-Custom-Ts")
        monkeypatch.setattr("src.main.time", lambda: 1700000000)
        body = b'{"a":1}'
        headers = _build_headers(body)
        assert headers["X-Custom-Ts"] == "1700000000"
        assert headers["X-Custom-Sig"] == self._expected("1700000000", "s3cret", body)
        assert "X-Webhook-Signature-V2" not in headers
        assert "X-Webhook-Timestamp" not in headers

    def test_send_posts_signed_body(self, monkeypatch):
        monkeypatch.setattr("src.main.config.hmac_secret", "s3cret")
        monkeypatch.setattr("src.main.time", lambda: 1700000000)
        captured = {}

        def fake_post(url, data, headers):
            captured["url"] = url
            captured["data"] = data
            captured["headers"] = headers

        monkeypatch.setattr("src.main.requests.post", fake_post)
        monkeypatch.setattr("src.main._fetch_disclosure_links", lambda edge_no: None)
        wh = GenericWebhook("https://listener.example.com/hook", TestGenericWebhook._item())
        wh.send()

        body = json.dumps(wh._format_data()).encode()
        assert captured["url"] == "https://listener.example.com/hook"
        assert captured["data"] == body
        assert captured["headers"]["Content-Type"] == "application/json"
        assert captured["headers"]["X-Webhook-Timestamp"] == "1700000000"
        assert captured["headers"]["X-Webhook-Signature-V2"] == self._expected("1700000000", "s3cret", body)
