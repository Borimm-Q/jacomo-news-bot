"""일반 코인 뉴스 수집 (CryptoPanic 무료 API).

CryptoPanic 은 여러 매체의 기사를 모아 '제목 + 출처 + 링크'만 제공합니다.
본문 전체를 가져오지 않으므로(=우리가 복제할 원문 문장이 없음) 법적으로 안전하고,
우리는 제목의 '사실'만 받아 Claude 로 한국어로 새로 씁니다.

API 문서: https://cryptopanic.com/developers/api/
"""
from datetime import datetime

import requests

import config

_URL = "https://cryptopanic.com/api/v1/posts/"


def _parse_iso(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def collect() -> list[dict]:
    token = config.CRYPTOPANIC_TOKEN()
    if not token:
        print("[news] CRYPTOPANIC_TOKEN 이 없어 뉴스 수집을 건너뜁니다.")
        return []

    try:
        resp = requests.get(
            _URL,
            params={
                "auth_token": token,
                "public": "true",
                "kind": "news",   # media/blog 제외, 뉴스만
            },
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"[news] CryptoPanic 수집 실패: {exc}")
        return []

    items: list[dict] = []
    for post in results:
        post_id = post.get("id")
        title = (post.get("title") or "").strip()
        url = post.get("url") or ""
        if not post_id or not title:
            continue
        source = post.get("source") or {}
        source_name = source.get("title") or source.get("domain") or "코인 뉴스"
        items.append(
            {
                "id": f"cryptopanic:{post_id}",
                "source_type": "crypto",
                "source_name": source_name,
                "title": title,
                "url": url,
                "body": "",
                "published_at": _parse_iso(post.get("published_at") or post.get("created_at")),
            }
        )
    return items
