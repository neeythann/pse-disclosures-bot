from bs4 import BeautifulSoup
from src.main import create_webhook, DiscordWebhook, SlackWebhook, GenericWebhook, Webhook


class TestCreateWebhook:

    def test_discord_com_url_returns_discord_webhook(self):
        wh = create_webhook("https://discord.com/api/webhooks/123", None)
        assert isinstance(wh, DiscordWebhook)
        assert isinstance(wh, Webhook)


    def test_discordapp_com_url_returns_discord_webhook(self):
        wh = create_webhook("https://discordapp.com/api/webhooks/123", None)
        assert isinstance(wh, DiscordWebhook)


    def test_hooks_slack_com_url_returns_slack_webhook(self):
        wh = create_webhook("https://hooks.slack.com/services/T0001/B0001/XXXXXXXX", None)
        assert isinstance(wh, SlackWebhook)
        assert isinstance(wh, Webhook)


    def test_unknown_host_falls_back_to_generic(self):
        wh = create_webhook("https://example.com/hook", None)
        assert isinstance(wh, GenericWebhook)
        assert isinstance(wh, Webhook)


class TestSlackWebhookFormat:

    @staticmethod
    def _disclosure():
        with open("./tests/html/disclosure.html") as f:
            from src.main import CompanyDisclosure
            return CompanyDisclosure.parse_tag(BeautifulSoup(f.read(), "html.parser"))[0]

    def test_format_translates_discord_embed_to_slack_attachment(self):
        item = self._disclosure()
        attachment = SlackWebhook("https://hooks.slack.com/services/T/B/X", item)._format_data()["attachments"][0]

        assert attachment["author_name"] == item.company_name
        assert attachment["author_link"] == "https://edge.pse.com.ph{}".format(item._id)
        assert attachment["title"] == item.title
        assert attachment["title_link"] == "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}".format(item.edge_no)
        assert attachment["footer"] == item.date
        assert [{"title": f["title"], "value": f["value"], "short": f["short"]} for f in attachment["fields"]] == [
            {"title": "Circular number", "value": item.circular_number, "short": True},
            {"title": "Form Type", "value": item.form_type, "short": True},
        ]
