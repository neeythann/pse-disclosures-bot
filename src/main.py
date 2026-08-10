from __future__ import annotations

import hashlib
import hmac
import json
import random
import re
import requests
import logging

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from dataclasses import asdict, dataclass
from time import sleep
from typing import Dict, Any, List, Union
from urllib.parse import urlparse

from .config import Config
from .db import Database

config = Config()

TABLE_BY_KEY = {
    "announcement": "company_disclosures",
    "financial": "company_disclosures",
    "other": "company_disclosures",
    "dividends": "dividends",
    "rights": "stock_rights",
}

OPEN_DISC_VIEWER_URL = "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}"
DOWNLOAD_FILE_URL = "https://edge.pse.com.ph/downloadFile.do?file_id={}"

_disclosure_links_cache: Dict[str, Dict[str, Any]] = {}


def _rows(soup: Tag) -> List[Tag]:
    assert soup.table is not None
    assert soup.table.tbody is not None
    return [r for r in soup.table.tbody if not isinstance(r, NavigableString)]


def _cell_text(cell: Tag) -> str:
    return cell.get_text()


def _edge_no(cell: Tag) -> str:
    a = cell.find("a")
    return a["onclick"].split("'")[1] #pyright: ignore


class Webhook:
    url: str
    data: Any

    def _format_data(self) -> Dict[Any, Any]:
        raise NotImplementedError

    def send(self) -> None:
        payload = self._format_data()
        body = json.dumps(payload).encode()
        headers = _build_headers(body)
        requests.post(self.url, data=body, headers=headers)


def _build_headers(body: bytes) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if config.hmac_secret:
        digest = hmac.new(config.hmac_secret.encode(), body, hashlib.sha256).hexdigest()
        headers["X-HMAC-Signature"] = "sha256={}".format(digest)
    return headers


@dataclass
class DiscordWebhook(Webhook):
    url: str
    data: Union["CompanyDisclosure", "Dividend", "StockRights"]

    def _format_data(self) -> Dict[Any, Any]:
        return {
            "username": "PSE Disclosure",
            "avatar_url": "",
            "embeds": [self.data.to_embed()],
        }


@dataclass
class SlackWebhook(Webhook):
    url: str
    data: Union["CompanyDisclosure", "Dividend", "StockRights"]

    def _format_data(self) -> Dict[Any, Any]:
        embed = self.data.to_embed()
        attachment: Dict[Any, Any] = {}
        author = embed.get("author")
        if author:
            if author.get("name"):
                attachment["author_name"] = author["name"]
            if author.get("url"):
                attachment["author_link"] = author["url"]
        if embed.get("title"):
            attachment["title"] = embed["title"]
        if embed.get("url"):
            attachment["title_link"] = embed["url"]
        fields = embed.get("fields")
        if fields:
            attachment["fields"] = [
                {"title": f["name"], "value": f["value"], "short": f.get("inline", False)}
                for f in fields
            ]
        footer = embed.get("footer")
        if footer and footer.get("text"):
            attachment["footer"] = footer["text"]
        return {"attachments": [attachment]}


@dataclass
class GenericWebhook(Webhook):
    url: str
    data: Union["CompanyDisclosure", "Dividend", "StockRights"]

    def _format_data(self) -> Dict[Any, Any]:
        payload: Dict[Any, Any] = {
            "type": type(self.data).__name__,
            "object": asdict(self.data),
            "viewer_url": OPEN_DISC_VIEWER_URL.format(self.data.edge_no),
        }
        links = _fetch_disclosure_links(self.data.edge_no)
        if links is not None:
            payload["main_doc_url"] = links["main_doc_url"]
            payload["attachment_links"] = links["attachment_links"]
        else:
            logging.error("Could not fetch disclosure links for edge_no {}".format(self.data.edge_no))
        return payload


def create_webhook(url: str, data: Any) -> Webhook:
    host = urlparse(url).netloc.lower()
    if "discord.com" in host or "discordapp.com" in host:
        return DiscordWebhook(url, data)
    if "hooks.slack.com" in host:
        return SlackWebhook(url, data)
    return GenericWebhook(url, data)


@dataclass(unsafe_hash=True)
class CompanyDisclosure:
    _id: str
    company_name: str
    title: str
    edge_no: str
    form_type: str
    date: str
    circular_number: str

    @staticmethod
    def parse_tag(soup: Tag) -> List[CompanyDisclosure]:
        return [CompanyDisclosure.parse(r) for r in _rows(soup)]

    @classmethod
    def parse(cls, row: Tag) -> CompanyDisclosure:
        tds = row.find_all("td")
        company_a = tds[0].find("a")
        return cls(
            _id=company_a["href"], #pyright: ignore
            company_name=_cell_text(tds[0]),
            edge_no=_edge_no(tds[1]),
            title=_cell_text(tds[1]),
            form_type=_cell_text(tds[2]),
            date=_cell_text(tds[3]),
            circular_number=_cell_text(tds[4]),
        )

    def to_embed(self) -> Dict[Any, Any]:
        return {
            "author": {
                "name": self.company_name,
                "url": "https://edge.pse.com.ph{}".format(self._id)
            },
            "title": self.title,
            "url": "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}".format(self.edge_no),
            "fields": [
                {
                    "name": "Circular number",
                    "value": self.circular_number,
                    "inline": True
                },
                {
                    "name": "Form Type",
                    "value": self.form_type,
                    "inline": True
                },
            ],
            "footer": {
                "text": self.date
            }
        }


@dataclass(unsafe_hash=True)
class Dividend:
    _id: str
    company_name: str
    security_type: str
    dividend_type: str
    rate: str
    ex_date: str
    record_date: str
    payment_date: str
    edge_no: str
    circular_number: str

    @staticmethod
    def parse_tag(soup: Tag) -> List[Dividend]:
        return [Dividend.parse(r) for r in _rows(soup)]

    @classmethod
    def parse(cls, row: Tag) -> Dividend:
        tds = row.find_all("td")
        company_a = tds[0].find("a")
        return cls(
            _id=company_a["href"], #pyright: ignore
            company_name=_cell_text(tds[0]),
            security_type=_cell_text(tds[1]),
            dividend_type=_cell_text(tds[2]),
            rate=_cell_text(tds[3]),
            ex_date=_cell_text(tds[4]),
            record_date=_cell_text(tds[5]),
            payment_date=_cell_text(tds[6]),
            edge_no=_edge_no(tds[-1]),
            circular_number=_cell_text(tds[-1]),
        )

    def to_embed(self) -> Dict[Any, Any]:
        return {
            "author": {
                "name": self.company_name,
                "url": "https://edge.pse.com.ph{}".format(self._id)
            },
            "title": "{} Dividend - {}".format(self.dividend_type, self.security_type),
            "url": "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}".format(self.edge_no),
            "fields": [
                {
                    "name": "Dividend Rate",
                    "value": self.rate,
                    "inline": True
                },
                {
                    "name": "Ex-Dividend Date",
                    "value": self.ex_date,
                    "inline": True
                },
                {
                    "name": "Record Date",
                    "value": self.record_date,
                    "inline": True
                },
                {
                    "name": "Payment Date",
                    "value": self.payment_date,
                    "inline": True
                },
            ],
            "footer": {
                "text": self.circular_number
            }
        }


@dataclass(unsafe_hash=True)
class StockRights:
    _id: str
    company_name: str
    entitlement_ratio: str
    offer_price: str
    ex_rights_date: str
    offer_start: str
    offer_end: str
    edge_no: str
    circular_number: str

    @staticmethod
    def parse_tag(soup: Tag) -> List[StockRights]:
        return [StockRights.parse(r) for r in _rows(soup)]

    @classmethod
    def parse(cls, row: Tag) -> StockRights:
        tds = row.find_all("td")
        company_a = tds[0].find("a")
        return cls(
            _id=company_a["href"], #pyright: ignore
            company_name=_cell_text(tds[0]),
            entitlement_ratio=_cell_text(tds[1]),
            offer_price=_cell_text(tds[2]),
            ex_rights_date=_cell_text(tds[3]),
            offer_start=_cell_text(tds[4]),
            offer_end=_cell_text(tds[5]),
            edge_no=_edge_no(tds[-1]),
            circular_number=_cell_text(tds[-1]),
        )

    def to_embed(self) -> Dict[Any, Any]:
        return {
            "author": {
                "name": self.company_name,
                "url": "https://edge.pse.com.ph{}".format(self._id)
            },
            "title": "Stock Rights Offering",
            "url": "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}".format(self.edge_no),
            "fields": [
                {
                    "name": "Entitlement Ratio",
                    "value": self.entitlement_ratio,
                    "inline": True
                },
                {
                    "name": "Offer Price",
                    "value": self.offer_price,
                    "inline": True
                },
                {
                    "name": "Ex-Rights Date",
                    "value": self.ex_rights_date,
                    "inline": True
                },
                {
                    "name": "Offer Start",
                    "value": self.offer_start,
                    "inline": True
                },
                {
                    "name": "Offer End",
                    "value": self.offer_end,
                    "inline": True
                },
            ],
            "footer": {
                "text": self.circular_number
            }
        }


def _fetch(key: str, url: str, data: Dict[str, str] = None) -> Any: #pyright: ignore
    if data is not None:
        response = requests.post(url, data=data, headers=config.headers)
    else:
        response = requests.get(url, headers=config.headers)

    if response is None:
        logging.error("Got empty response on endpoint: {}".format(key))
        return None

    if response.status_code != 200:
        logging.error("Got response status: {}".format(response.status_code))
        return None

    return response


def _parse_viewer_links(soup: Tag) -> Dict[str, Any]:
    main_doc_url = ""
    iframe = soup.find("iframe", id="viewContents")
    if iframe is not None and iframe.get("src"):
        main_doc_url = "https://edge.pse.com.ph{}".format(iframe["src"])

    attachment_links: List[Dict[str, str]] = []
    file_list = soup.find("select", id="file_list")
    if file_list is not None:
        for option in file_list.find_all("option"):
            file_id = option.get("value")
            if file_id:
                attachment_links.append({
                    "name": re.sub(r"\s+", " ", option.get_text()).strip(),
                    "url": DOWNLOAD_FILE_URL.format(file_id),
                })

    return {
        "main_doc_url": main_doc_url,
        "attachment_links": attachment_links,
    }


def _fetch_disclosure_links(edge_no: str) -> Dict[str, Any]:
    if edge_no in _disclosure_links_cache:
        return _disclosure_links_cache[edge_no]
    response = requests.get(OPEN_DISC_VIEWER_URL.format(edge_no), headers=config.headers)
    if response.status_code != 200:
        return None #pyright: ignore
    soup = BeautifulSoup(response.content, 'html.parser')
    links = _parse_viewer_links(soup)
    _disclosure_links_cache[edge_no] = links
    return links


def _notify(items: List[Any]) -> None:
    for item in items:
        if config.mode in ("both", "webhook"):
            for url in config.webhook_urls:
                create_webhook(url, item).send() #pyright: ignore
        logging.info("New disclosure found: {}".format(item.circular_number))


def _diff_and_send(key: str, curr: List[Any], db: Database) -> None:
    table = TABLE_BY_KEY[key]

    if db.is_empty(table) and curr:
        db.insert(table, curr)
        logging.info("Seeded {} with {} initial items".format(table, len(curr)))
        return

    existing = db.get_existing_edge_nos(table, [item.edge_no for item in curr])
    new_items = [item for item in curr if item.edge_no not in existing]
    if not new_items:
        return

    _notify(new_items)
    db.insert(table, new_items)


def _diff_and_send_mem(key: str, curr: List[Any], cache: Dict[str, list]) -> None:
    if key not in cache:
        logging.info("Cache is empty, supplying current scraped data to cache")
        cache[key] = curr
        return

    if cache[key] != curr:
        diff = list(set(curr) - set(cache[key]))
        _notify(diff)
        cache[key] = curr


def main():
    data = {"fromDate": "10-10-25", "toDate": "10-11-2099"}
    db = Database() if config.mode in ("both", "archive") else None
    cache: Dict[str, list] = {}

    if config.mode == "archive":
        logging.info("Running in archive-only mode (no webhook notifications)")
    elif config.mode == "webhook":
        logging.info("Running in webhook-only mode (no SQLite archive; restarts may re-send)")

    # TODO: wrap in exceptions
    while True:
        for key, value in config.api_urls.items():
            response = _fetch(key, value, data)
            if response is None:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            curr = CompanyDisclosure.parse_tag(soup)
            if db is not None:
                _diff_and_send(key, curr, db)
            else:
                _diff_and_send_mem(key, curr, cache)
            sleep(random.randint(2, 5))

        for key, value in config.dividends_rights_urls.items():
            response = _fetch(key, value)
            if response is None:
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            if key == "dividends":
                curr = Dividend.parse_tag(soup)
            else:
                curr = StockRights.parse_tag(soup)
            if db is not None:
                _diff_and_send(key, curr, db)
            else:
                _diff_and_send_mem(key, curr, cache)
            sleep(random.randint(2, 5))

        sleep(config.poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
