from __future__ import annotations

import random
import requests
import logging

from bs4 import BeautifulSoup
from bs4.element import NavigableString, PageElement, Tag
from dataclasses import dataclass
from os import getenv
from time import sleep
from typing import Dict, Any, List

from .config import API_URLS

WEBHOOK_URL = getenv("WEBHOOK_URL")
if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL is not set")
POLL_INTERVAL = 60 * 5 # 5 mins


@dataclass
class DiscordWebhook:
    url: str
    data: CompanyDisclosure

    def _format_data(self) -> Dict[Any, Any]:
        return {
            "username": "PSE Disclosure",
            "avatar_url": "",
            "embeds": [
                {
                    "author": {
                        "name": self.data.company_name,
                        "url": "https://edge.pse.com.ph{}".format(self.data._id)
                    },
                    "title": self.data.title,
                    "url": "https://edge.pse.com.ph/openDiscViewer.do?edge_no={}".format(self.data.edge_no),
                    "fields": [
                        {
                            "name":"Circular number",
                            "value": self.data.circular_number,
                            "inline": True
                        },
                        {
                            "name":"Form Type",
                            "value": self.data.form_type,
                            "inline": True
                        },
                    ],
                    "footer": {
                        "text": self.data.date
                    }
                },
            ]
        }

    def send(self) -> None:
        requests.post(self.url, json=self._format_data(), headers={"Content-Type": "application/json"})


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
        rtn = []

        assert soup.table is not None
        assert soup.table.tbody is not None

        for company in soup.table.tbody:
            if isinstance(company, NavigableString):
                continue
            rtn.append(CompanyDisclosure.parse(company))

        return rtn

    # TODO(nathan): refactor this linked list madness and add element validation
    @classmethod
    def parse(cls, data: PageElement) -> CompanyDisclosure:
        data = data.next_element.next_element.next_element #pyright: ignore

        _id = data['href'] #pyright: ignore
        company_name = data.text
        data = data.next_element.next_element.next_element.next_element #pyright: ignore

        edge_no = data['onclick'].split("'")[1] #pyright: ignore
        data = data.next_element #pyright: ignore

        title = data.text
        data = data.next_element.next_element.next_element #pyright: ignore

        form_type = data.text
        data = data.next_element.next_element.next_element #pyright: ignore

        date = data.text
        data = data.next_element.next_element.next_element #pyright: ignore

        circular_number = data.text
        return cls(_id, company_name, title, edge_no, form_type, date, circular_number)


def main():
    # pragmatic engineering here lol
    data = {"fromDate": "10-10-25", "toDate": "10-11-2099"}
    cache: Dict[str, List[CompanyDisclosure]] = {}

    # TODO: wrap in exceptions
    while True:
        for key, value in API_URLS.items():
            response = requests.post(value, data=data, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.149 Safari/537.36"})

            if response is None:
                logging.error("Got empty response on endpoint: {}".format(key))
                continue

            if response.status_code != 200:
                logging.error("Got response status: {}".format(response.status_code))
                continue

            soup = BeautifulSoup(response.content, 'html.parser')
            curr = CompanyDisclosure.parse_tag(soup)

            if key not in cache:
                logging.info("Cache is empty, supplying current scraped data to cache")
                cache[key] = curr
                continue

            if cache[key] != curr:
                diff = list(set(curr) - set(cache[key]))
                for item in diff:
                    DiscordWebhook(WEBHOOK_URL, item).send() #pyright: ignore
                    logging.info("New disclosure found: {}".format(item.circular_number))

                cache[key] = curr

            sleep(random.randint(2,5))

        sleep(POLL_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
