from bs4 import BeautifulSoup
from src.db import Database
from src.main import CompanyDisclosure, Dividend, StockRights

class TestDatabase:

    @staticmethod
    def _load(name: str) -> str:
        with open("./tests/html/{}.html".format(name)) as f:
            return f.read()


    def test_is_empty_initially(self):
        db = Database(":memory:")
        assert db.is_empty("company_disclosures")
        assert db.is_empty("dividends")
        assert db.is_empty("stock_rights")
        db.close()


    def test_seed_does_not_send_and_populates(self):
        db = Database(":memory:")
        items = CompanyDisclosure.parse_tag(BeautifulSoup(self._load("disclosure"), 'html.parser'))
        assert db.is_empty("company_disclosures")
        db.insert("company_disclosures", items)
        assert not db.is_empty("company_disclosures")
        db.close()


    def test_dedup_finds_existing(self):
        db = Database(":memory:")
        items = Dividend.parse_tag(BeautifulSoup(self._load("dividends"), 'html.parser'))
        db.insert("dividends", items)
        existing = db.get_existing_edge_nos("dividends", [i.edge_no for i in items])
        assert existing == {i.edge_no for i in items}
        db.close()


    def test_dedup_ignores_unknown(self):
        db = Database(":memory:")
        assert db.get_existing_edge_nos("stock_rights", ["nonexistent"]) == set()
        db.close()


    def test_insert_is_idempotent(self):
        db = Database(":memory:")
        items = StockRights.parse_tag(BeautifulSoup(self._load("rights"), 'html.parser'))
        db.insert("stock_rights", items)
        db.insert("stock_rights", items)
        existing = db.get_existing_edge_nos("stock_rights", [i.edge_no for i in items])
        assert len(existing) == len(items)
        db.close()
