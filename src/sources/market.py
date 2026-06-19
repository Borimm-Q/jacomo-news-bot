"""시장·매크로·지정학 뉴스 수집 (Finnhub 무료 API).

Finnhub 의 시장 뉴스 엔드포인트는 무료 키 하나로 아래 카테고리를 제공합니다:
    general (일반 경제·지정학·정책), forex (환율), crypto (코인), merger (M&A)
각 항목은 제목 + 짧은 요약 + 출처 + 링크 형태라, 우리는 '사실'만 받아
한국어로 새로 씁니다.

API 문서: https://finnhub.io/docs/api/market-news
"""
import requests

import config

_URL = "https://finnhub.io/api/v1/news"

# 수집할 카테고리 → 우리 내부 분류(source_type)
# crypto 는 '코인', 나머지(general/forex/merger)는 '시장·경제'로 묶는다.
_CATEGORIES = {
    "general": "market",
    "forex": "market",
    "merger": "market",
    "crypto": "crypto",
}


def collect() -> list[dict]:
    token = config.FINNHUB_TOKEN()
    if not token:
        print("[market] FINNHUB_TOKEN 이 없어 시장 뉴스 수집을 건너뜁니다.")
        return []

    items: list[dict] = []
    seen_ids: set[str] = set()  # 카테고리 간 중복 제거

    for category, internal_type in _CATEGORIES.items():
        try:
            resp = requests.get(
                _URL,
                params={"category": category, "token": token},
                timeout=20,
            )
            resp.raise_for_status()
            articles = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[market] Finnhub '{category}' 수집 실패(건너뜀): {exc}")
            continue

        count = 0
        for a in articles or []:
            aid = a.get("id")
            headline = (a.get("headline") or "").strip()
            url = a.get("url") or ""
            if not aid or not headline:
                continue
            item_id = f"finnhub:{aid}"
            if item_id in seen_ids:
                continue
            seen_ids.add(item_id)
            items.append(
                {
                    "id": item_id,
                    "source_type": internal_type,
                    "source_name": a.get("source") or "시장 뉴스",
                    "title": headline,
                    "url": url,
                    "body": (a.get("summary") or "").strip(),
                }
            )
            count += 1
        print(f"[market] Finnhub {category}: {count}건 수집")

    return items
