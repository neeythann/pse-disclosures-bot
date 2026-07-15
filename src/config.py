from __future__ import annotations

import os
from typing import Dict, List


API_URLS: Dict[str, str] = {
    "announcement": "https://edge.pse.com.ph/announcements/search.ax",
    "financial": "https://edge.pse.com.ph/financialReports/search.ax",
    "other": "https://edge.pse.com.ph/otherReports/search.ax",
}

DIVIDENDS_RIGHTS_URLS: Dict[str, str] = {
    "dividends": "https://edge.pse.com.ph/disclosureData/dividends_and_rights_info_list.ax?DividendsOrRights=Dividends",
    "rights": "https://edge.pse.com.ph/disclosureData/dividends_and_rights_info_list.ax?DividendsOrRights=Rights",
}


class Config:
    _instance: "Config | None" = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            inst = super().__new__(cls)
            mode = (os.getenv("OUTPUT_MODE") or "both").strip().lower()
            if mode not in ("both", "archive", "webhook"):
                raise ValueError("OUTPUT_MODE must be 'both', 'archive', or 'webhook'; got {!r}".format(mode))
            webhook_urls: List[str] = [
                u.strip() for u in (os.getenv("WEBHOOK_URL") or "").split(",") if u.strip()
            ]
            if mode in ("both", "webhook") and not webhook_urls:
                raise ValueError("WEBHOOK_URL is required when OUTPUT_MODE is 'both' or 'webhook'")
            inst.webhook_urls = webhook_urls
            inst.mode = mode
            inst.poll_interval = 60 * 5 # 5 mins
            inst.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.5938.149 Safari/537.36"}
            inst.api_urls = API_URLS
            inst.dividends_rights_urls = DIVIDENDS_RIGHTS_URLS
            cls._instance = inst
        return cls._instance
