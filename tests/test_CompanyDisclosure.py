from bs4 import BeautifulSoup
from src.main import CompanyDisclosure

class TestCompanyDisclosure:

    @staticmethod
    def _load_testcase() -> str:
        with open("./tests/html/disclosure.html") as f:
            return f.read()


    def test_CompanyDisclosure_parse(self):
        response = TestCompanyDisclosure._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = CompanyDisclosure.parse_tag(soup)
        assert len(curr) == 50


    def test_CompanyDisclosure__eq__(self):
        response = TestCompanyDisclosure._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        curr = CompanyDisclosure.parse_tag(soup)
        assert curr[0] == curr[0]


    def test_CompanyDisclosure_diff(self):
        response = TestCompanyDisclosure._load_testcase()
        soup = BeautifulSoup(response, 'html.parser')
        cache = CompanyDisclosure.parse_tag(soup)
        rtn = cache[0]
        curr = cache.copy()
        cache = cache[1:len(cache)]
        curr = curr[:len(curr) - 1]
        diff = list(set(curr) - set(cache))
        assert diff[0] == rtn

