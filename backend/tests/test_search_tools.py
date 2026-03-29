import pytest
from app.tools.search_tools import web_search

def test_web_search():
    result = web_search("Python programming")
    assert isinstance(result, str)
    assert len(result) > 0

def test_web_search_with_max_results():
    result = web_search("AI", max_results=3)
    assert isinstance(result, str)
