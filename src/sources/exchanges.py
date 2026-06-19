"""거래소 공식 공지 수집.

거래소가 직접 발표한 공지(상장/이벤트/점검 등)는 '공식 1차 출처'라 가장 안전합니다.
각 거래소 엔드포인트는 비공식이라 응답 구조가 바뀔 수 있으므로, 각 수집기는 예외를
자체 처리하고 실패 시 빈 리스트를 반환합니다.

NOTE: 실제 운영 전 각 엔드포인트의 응답을 한 번 확인하세요(README 의 검증 절차 참고).
막히는 거래소는 비활성화하거나 공식 공지 RSS 로 대체하면 됩니다.
"""
import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def _upbit() -> list[dict]:
    """업비트 공지 (한국 최대 거래소 — 한국인 대상으로 가장 중요)."""
    url = "https://api-manager.upbit.com/api/v1/announcements"
    params = {"os": "web", "page": 1, "per_page": 20, "category": "all"}
    resp = requests.get(url, params=params, headers={**_HEADERS, "Referer": "https://upbit.com/"}, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    notices = data.get("notices") or data.get("list") or []
    items = []
    for n in notices:
        nid = n.get("id")
        title = (n.get("title") or "").strip()
        if not nid or not title:
            continue
        items.append(
            {
                "id": f"upbit:{nid}",
                "source_type": "exchange",
                "source_name": "업비트",
                "title": title,
                "url": f"https://upbit.com/service_center/notice?id={nid}",
                "body": "",
            }
        )
    return items


def _binance() -> list[dict]:
    """바이낸스 공지 (글로벌 1위 거래소)."""
    url = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
    params = {"type": 1, "catalogId": 48, "pageNo": 1, "pageSize": 20}
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", {})
    articles = []
    for catalog in data.get("catalogs", []) or []:
        articles.extend(catalog.get("articles", []) or [])
    articles.extend(data.get("articles", []) or [])

    items = []
    for a in articles:
        code = a.get("code")
        title = (a.get("title") or "").strip()
        if not code or not title:
            continue
        items.append(
            {
                "id": f"binance:{code}",
                "source_type": "exchange",
                "source_name": "바이낸스",
                "title": title,
                "url": f"https://www.binance.com/en/support/announcement/{code}",
                "body": "",
            }
        )
    return items


def _okx() -> list[dict]:
    """OKX 공지 (한국 사용자 다수, 신규 상장/이벤트/거래 업데이트)."""
    url = "https://www.okx.com/api/v5/support/announcements"
    resp = requests.get(url, params={"page": 1}, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    items = []
    for block in data:
        for n in block.get("details", []) or []:
            title = (n.get("title") or "").strip()
            link = n.get("url") or ""
            if not title or not link:
                continue
            items.append(
                {
                    "id": f"okx:{link}",
                    "source_type": "exchange",
                    "source_name": "OKX",
                    "title": title,
                    "url": link,
                    "body": "",
                }
            )
    return items


def _kucoin() -> list[dict]:
    """KuCoin 공지."""
    url = "https://api.kucoin.com/api/v3/announcements"
    params = {"currentPage": 1, "pageSize": 20, "lang": "en_US"}
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    items_raw = (resp.json().get("data") or {}).get("items", [])
    items = []
    for n in items_raw:
        aid = n.get("annId")
        title = (n.get("annTitle") or "").strip()
        link = n.get("annUrl") or ""
        if not aid or not title:
            continue
        items.append(
            {
                "id": f"kucoin:{aid}",
                "source_type": "exchange",
                "source_name": "KuCoin",
                "title": title,
                "url": link,
                "body": (n.get("annDesc") or "").strip(),
            }
        )
    return items


# 활성 수집기 목록. 문제가 생기면 여기서 주석 처리하면 됩니다.
# (빗썸은 Cloudflare 차단으로 제외 — 한국 거래소는 업비트로 커버)
_FETCHERS = [
    ("업비트", _upbit),
    ("바이낸스", _binance),
    ("OKX", _okx),
    ("KuCoin", _kucoin),
]


def collect() -> list[dict]:
    items: list[dict] = []
    for name, fetcher in _FETCHERS:
        try:
            fetched = fetcher()
            items.extend(fetched)
            print(f"[exchange] {name}: {len(fetched)}건 수집")
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"[exchange] {name} 수집 실패(건너뜀): {exc}")
    return items
