"""
レシピ抽出API (Port 8004)
指定URLからレシピ名・材料・作り方を抽出して返却する
対応: 一般Webページ（JSON-LD）/ YouTube（Data API v3 + 説明文パース）
"""

import json
import os
import re
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from bs4 import BeautifulSoup

load_dotenv()

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

app = FastAPI(title="Recipe Scraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================
# YouTube
# ==============================================================

_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|shorts/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str | None:
    """YouTube URLから動画IDを抽出する"""
    m = _YOUTUBE_ID_RE.search(url)
    return m.group(1) if m else None


async def fetch_youtube_snippet(video_id: str) -> dict | None:
    """YouTube Data API v3 で動画のタイトルと説明文を取得する"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY},
        )
        resp.raise_for_status()
    items = resp.json().get("items", [])
    if not items:
        return None
    snippet = items[0]["snippet"]
    return {
        "title": snippet.get("title", "").strip(),
        "description": snippet.get("description", ""),
    }


# --- 説明文パーサー ---

# ーーーー / ──── / ---- 等の区切り行
_SEPARATOR_RE = re.compile(r"^[ーｰ─━\-]{3,}$")
# 【レシピ名】形式の行（後ろに(2人前)等が続く場合も含む）
_RECIPE_BLOCK_NAME_RE = re.compile(r"^【.+】")
# 食材名…分量 または 食材名...分量 形式（40文字以内）
_INGREDIENT_ELLIPSIS_RE = re.compile(r"^.+(?:…|\.{3}).+$")

_INGREDIENT_HEADER_RE = re.compile(
    r"【[^】]*材料[^】]*】"   # 【材料】【材料（2人分）】等
    r"|[◆▼●■▶▷→►]\s*材料"  # ◆材料 ▼材料 等
    r"|^材料"                  # 材料 / 材料（2人分）/ 材料：等（行頭）
)

_INSTRUCTION_HEADER_RE = re.compile(
    r"【[^】]*(?:作り方|手順|調理)[^】]*】"  # 【作り方】【手順】等
    r"|[◆▼●■▶▷→►]\s*(?:作り方|手順)"      # ◆作り方 ▼手順 等
    r"|^(?:作り方|手順)"                     # 作り方 / 手順（行頭）
)

# 上記以外のセクションヘッダー（収集停止トリガー）
_OTHER_SECTION_RE = re.compile(
    r"【[^】]+】"
    r"|[◆▼●■▶▷→►]\s*\S"
)

_LEADING_BULLET_RE = re.compile(r"^[・\-•–—→►▶✓☑]\s*")
_LEADING_NUMBER_RE = re.compile(r"^(?:\d+[.)）]\s*|[①-⑳⑴-⑽]\s*)")


def _clean_line(line: str) -> str:
    line = _LEADING_BULLET_RE.sub("", line)
    line = _LEADING_NUMBER_RE.sub("", line)
    return line.strip()


def _parse_by_headers(description: str) -> dict:
    """【材料】◆作り方 等のヘッダー形式で材料・作り方を抽出する"""
    ingredients: list[str] = []
    instructions: list[str] = []
    current_section: str | None = None

    for raw_line in description.splitlines():
        line = raw_line.strip()

        if _INGREDIENT_HEADER_RE.search(line):
            current_section = "ingredients"
            continue

        if _INSTRUCTION_HEADER_RE.search(line):
            current_section = "instructions"
            continue

        if _OTHER_SECTION_RE.search(line):
            current_section = None
            continue

        if not line:
            continue

        if current_section == "ingredients":
            ingredients.append(_clean_line(line))
        elif current_section == "instructions":
            instructions.append(_clean_line(line))

    return {
        "ingredients": ingredients or None,
        "instructions": instructions or None,
    }


def _parse_separator_block(description: str) -> dict:
    """ーーーー区切りブロック内の 食材名…分量 形式で材料・作り方を抽出する"""
    lines = description.splitlines()

    in_block = False
    block_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if _SEPARATOR_RE.match(stripped):
            if in_block:
                break  # ブロック終了
            else:
                in_block = True  # ブロック開始
                continue
        if in_block:
            block_lines.append(stripped)

    if not block_lines:
        return {"ingredients": None, "instructions": None}

    ingredients: list[str] = []
    instructions: list[str] = []

    for line in block_lines:
        if not line:
            continue
        # 【レシピ名】行はスキップ
        if _RECIPE_BLOCK_NAME_RE.match(line):
            continue
        # 食材名…分量 かつ短い行 → 材料
        if _INGREDIENT_ELLIPSIS_RE.match(line) and len(line) <= 40:
            ingredients.append(line)
        else:
            # ★や※等の先頭記号を除去して作り方として収集
            clean = re.sub(r"^[★※＊\*]\s*", "", line)
            if clean:
                instructions.append(clean)

    return {
        "ingredients": ingredients or None,
        "instructions": instructions or None,
    }


def parse_recipe_from_description(description: str) -> dict:
    """YouTube説明文から材料・作り方を抽出する。
    ヘッダー形式（【材料】等）を優先し、取れなければ区切り形式（ーーーー）を試みる。
    """
    result = _parse_by_headers(description)
    if result["ingredients"] or result["instructions"]:
        return result

    return _parse_separator_block(description)


# ==============================================================
# Webスクレイピング（JSON-LD）
# ==============================================================

def _is_recipe_type(data: dict) -> bool:
    """dict が @type: Recipe かどうかを判定"""
    at_type = data.get("@type", "")
    types = at_type if isinstance(at_type, list) else [at_type]
    return "Recipe" in types


def _normalize_instructions(raw) -> list[str] | None:
    """recipeInstructions を文字列リストに正規化する。
    対応形式:
      - 文字列: "手順1。手順2。"
      - 文字列リスト: ["手順1", "手順2"]
      - HowToStep リスト: [{"@type": "HowToStep", "text": "手順1"}, ...]
      - HowToSection リスト: [{"@type": "HowToSection", "itemListElement": [...]}]
    """
    if not raw:
        return None

    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else None

    if not isinstance(raw, list):
        return None

    steps = []
    for item in raw:
        if isinstance(item, str):
            if item.strip():
                steps.append(item.strip())
        elif isinstance(item, dict):
            if item.get("@type") == "HowToSection":
                sub = _normalize_instructions(item.get("itemListElement"))
                if sub:
                    steps.extend(sub)
            else:
                text = item.get("text", "").strip()
                if text:
                    steps.append(text)

    return steps if steps else None


def _find_recipe_data(data: dict) -> dict | None:
    """dict から Recipe type のデータ（name / ingredients / instructions）を探す"""
    if _is_recipe_type(data):
        name = data.get("name", "").strip() or None
        ingredients = data.get("recipeIngredient") or None
        if isinstance(ingredients, list):
            ingredients = [i.strip() for i in ingredients if isinstance(i, str) and i.strip()] or None
        instructions = _normalize_instructions(data.get("recipeInstructions"))
        if name or ingredients or instructions:
            return {"name": name, "ingredients": ingredients, "instructions": instructions}

    for item in data.get("@graph", []):
        if isinstance(item, dict):
            result = _find_recipe_data(item)
            if result:
                return result
    return None


def extract_recipe_from_json_ld(soup: BeautifulSoup) -> dict | None:
    """JSON-LD (@type: Recipe) から name / ingredients / instructions を取得"""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        if isinstance(data, dict):
            result = _find_recipe_data(data)
            if result:
                return result

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    result = _find_recipe_data(item)
                    if result:
                        return result
    return None


def extract_title_from_og(soup: BeautifulSoup) -> str | None:
    """og:title から取得"""
    tag = soup.find("meta", property="og:title")
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def extract_title_from_title_tag(soup: BeautifulSoup) -> str | None:
    """<title> タグから取得"""
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def extract_source(url: str) -> str:
    """URLからドメイン名を抽出"""
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return re.sub(r"^www\.", "", host)


# ==============================================================
# エンドポイント
# ==============================================================

@app.get("/api/recipe/extract")
async def extract_recipe(
    url: str = Query(..., description="レシピページのURL"),
    debug: bool = Query(False, description="Trueにすると説明文の生テキストを返す（開発用）"),
):
    source = extract_source(url)

    # YouTube URL の場合は専用処理
    video_id = extract_video_id(url)
    if video_id:
        return await _extract_from_youtube(url, video_id, source, debug=debug)

    return await _extract_from_web(url, source)


async def _extract_from_youtube(url: str, video_id: str, source: str, debug: bool = False) -> dict:
    """YouTube Data API v3 で動画情報を取得し、説明文からレシピを抽出する"""
    if not YOUTUBE_API_KEY:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": "YOUTUBE_API_KEY が設定されていません",
        }

    try:
        snippet = await fetch_youtube_snippet(video_id)
    except httpx.HTTPStatusError as e:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": f"YouTube API エラー: HTTP {e.response.status_code}",
        }
    except httpx.RequestError as e:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": f"YouTube API 接続エラー: {type(e).__name__}",
        }

    if not snippet:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": "動画が見つかりません（非公開または削除済みの可能性があります）",
        }

    parsed = parse_recipe_from_description(snippet["description"])

    result = {
        "url": url,
        "title": snippet["title"],
        "source": source,
        "ingredients": parsed["ingredients"],
        "instructions": parsed["instructions"],
    }
    if debug:
        result["_debug_description"] = snippet["description"]
    return result


async def _extract_from_web(url: str, source: str) -> dict:
    """Webページから JSON-LD を使ってレシピを抽出する"""
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": f"HTTP {e.response.status_code}",
        }
    except httpx.RequestError as e:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": f"接続エラー: {type(e).__name__}",
        }

    soup = BeautifulSoup(resp.text, "html.parser")

    json_ld = extract_recipe_from_json_ld(soup)

    title = (
        (json_ld.get("name") if json_ld else None)
        or extract_title_from_og(soup)
        or extract_title_from_title_tag(soup)
    )
    ingredients = json_ld.get("ingredients") if json_ld else None
    instructions = json_ld.get("instructions") if json_ld else None

    if not title:
        return {
            "url": url,
            "title": None,
            "source": source,
            "ingredients": None,
            "instructions": None,
            "error": "タイトルを取得できませんでした",
        }

    return {
        "url": url,
        "title": title,
        "source": source,
        "ingredients": ingredients,
        "instructions": instructions,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
