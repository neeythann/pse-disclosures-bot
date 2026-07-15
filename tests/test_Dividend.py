from bs4 import BeautifulSoup
from src.main import Dividend

class TestDividend:

    @staticmethod
    def _load_testcase() -> str:
        with open("./tests/html/dividends.html") as f:
            return f.read()


    def test_Dividend_parse(self):
        response = TestDividend._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = Dividend.parse_tag(soup)
        assert len(curr) == 50


    def test_Dividend__eq__(self):
        response = TestDividend._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = Dividend.parse_tag(soup)
        assert curr[0] == curr[0]


    def test_Dividend_diff(self):
        response = TestDividend._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        cache = Dividend.parse_tag(soup)
        rtn = cache[0]
        curr = cache.copy()
        cache = cache[1:len(cache)]
        curr = curr[:len(curr) - 1]
        diff = list(set(curr) - set(cache))
        assert diff[0] == rtn
