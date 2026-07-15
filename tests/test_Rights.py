from bs4 import BeautifulSoup
from src.main import StockRights

class TestStockRights:

    @staticmethod
    def _load_testcase() -> str:
        with open("./tests/html/rights.html") as f:
            return f.read()


    def test_StockRights_parse(self):
        response = TestStockRights._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = StockRights.parse_tag(soup)
        assert len(curr) == 11


    def test_StockRights__eq__(self):
        response = TestStockRights._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = StockRights.parse_tag(soup)
        assert curr[0] == curr[0]


    def test_StockRights_diff(self):
        response = TestStockRights._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        cache = StockRights.parse_tag(soup)
        rtn = cache[0]
        curr = cache.copy()
        cache = cache[1:len(cache)]
        curr = curr[:len(curr) - 1]
        diff = list(set(curr) - set(cache))
        assert diff[0] == rtn
