import sys
from pathlib import Path
from unittest.mock import Mock

import dotenv

# Keep application import from searching for or reading the project .env file.
dotenv.load_dotenv = lambda *args, **kwargs: False
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

import recipe_scraper_api_app as app_module


SYNTHETIC_HTML = """
<html><head><title>Fallback title</title></head><body>
  <h1 itemprop="name">合成レシピ</h1>
  <section class="material">
    <ul class="disc-list"><li>じゃがいも　 2個</li><li>玉ねぎ <span>1個</span></li></ul>
    <ul class="a-list"><li>しょうゆ 大さじ1</li></ul>
  </section>
  <section class="howto">
    <div class="howto-block"><h3>下準備</h3><p>野菜を切る。</p>
      <p class="note-text small">補足は除外。</p></div>
    <div class="howto-block"><p>材料を煮る。</p></div>
    <div id="recipe_movie" class="howto-block"><p>動画案内は除外。</p></div>
  </section>
</body></html>
"""


def _client_for_html(monkeypatch, html):
    response = Mock(text=html)
    response.raise_for_status.return_value = None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url):
            return response

    monkeypatch.setattr(app_module.httpx, "AsyncClient", FakeAsyncClient)
    return TestClient(app_module.app)


def test_sirogohan_extracts_ingredients_and_steps():
    result = app_module._extract_sirogohan(BeautifulSoup(SYNTHETIC_HTML, "html.parser"))

    assert result == {
        "name": "合成レシピ",
        "ingredients": ["じゃがいも 2個", "玉ねぎ 1個", "A: しょうゆ 大さじ1"],
        "instructions": ["野菜を切る。", "材料を煮る。"],
    }


def test_json_ld_partial_recipe_does_not_call_site_extractor(monkeypatch):
    html = """<html><head><title>fallback</title>
      <script type="application/ld+json">{"@type":"Recipe","name":"JSON title",
      "recipeIngredient":["JSON item"]}</script></head><body></body></html>"""
    client = _client_for_html(monkeypatch, html)
    extractor = Mock(side_effect=AssertionError("site extractor must not run"))
    monkeypatch.setitem(app_module.SITE_EXTRACTORS, "sirogohan.com", extractor)

    response = client.get("/api/recipe/extract", params={"url": "https://www.sirogohan.com/r/"})

    assert response.status_code == 200
    assert response.json()["title"] == "JSON title"
    assert response.json()["ingredients"] == ["JSON item"]
    assert response.json()["instructions"] is None
    extractor.assert_not_called()


def test_sirogohan_endpoint_uses_site_extractor_without_network(monkeypatch):
    client = _client_for_html(monkeypatch, SYNTHETIC_HTML)

    response = client.get(
        "/api/recipe/extract",
        params={"url": "https://www.sirogohan.com/recipe/synthetic/"},
    )

    assert response.status_code == 200
    assert response.json()["title"] == "合成レシピ"
    assert response.json()["ingredients"] == ["じゃがいも 2個", "玉ねぎ 1個", "A: しょうゆ 大さじ1"]
    assert response.json()["instructions"] == ["野菜を切る。", "材料を煮る。"]


def test_unsupported_domain_keeps_title_only_fallback(monkeypatch):
    client = _client_for_html(monkeypatch, "<html><head><title>Only title</title></head></html>")

    response = client.get("/api/recipe/extract", params={"url": "https://example.test/recipe"})

    assert response.status_code == 200
    assert response.json()["title"] == "Only title"
    assert response.json()["ingredients"] is None
    assert response.json()["instructions"] is None


def test_empty_sirogohan_structure_returns_none_without_endpoint_error(monkeypatch):
    assert app_module._extract_sirogohan(BeautifulSoup("<html></html>", "html.parser")) is None
    client = _client_for_html(monkeypatch, "<html><head><title>Empty recipe</title></head></html>")

    response = client.get("/api/recipe/extract", params={"url": "https://sirogohan.com/empty"})

    assert response.status_code == 200
    assert response.json()["title"] == "Empty recipe"
    assert response.json()["ingredients"] is None
    assert response.json()["instructions"] is None
