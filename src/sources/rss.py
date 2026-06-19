"""RSS 피드 수집 (무료·합법).

특파원 김씨 출처 분석 결과, 그들이 가장 많이 인용하는 매체들은 대부분 무료 RSS 를
제공한다. 특히 1위 출처인 콜린 우(@WuBlockchain)도 Substack RSS 를 무료로 연다.
우리는 이 RSS 들의 '제목+요약(사실)'만 받아 Claude 로 한국어로 새로 쓴다.

표준 라이브러리(xml.etree)만 사용 — 모든 대상 피드가 RSS 2.0(<item>) 형식이다.
"""
import email.utils
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

# 일부 피드(Substack 등)가 봇 UA를 막아서, 일반 브라우저 UA로 위장
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# (출처명, 피드 URL, 내부 분류)
_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "crypto"),
    ("Cointelegraph", "https://cointelegraph.com/rss", "crypto"),
    ("The Block", "https://www.theblock.co/rss.xml", "crypto"),
    ("Decrypt", "https://decrypt.co/feed", "crypto"),
    # Wu Blockchain(Substack): GitHub Actions IP를 403 차단해서 제외 (한국 IP면 다시 추가 가능)
    # ("Wu Blockchain", "https://wublock.substack.com/feed", "crypto"),
    # 한국 코인 매체 (공식 RSS) — 코인니스 대신 1차 매체를 직접
    ("토큰포스트", "https://www.tokenpost.kr/rss", "crypto"),
    ("블록미디어", "https://www.blockmedia.co.kr/feed", "crypto"),
]

_TAG_RE = re.compile(r"<[^>]+>")


def _text(elem, tag: str) -> str:
    child = elem.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s).strip()


def _parse_date(elem) -> float | None:
    """RSS pubDate(RFC822) 또는 Atom published(ISO)를 epoch초로. 없으면 None."""
    for tag in ("pubDate", "published", "updated", "date"):
        t = _text(elem, tag)
        if not t:
            continue
        try:  # RFC822 (RSS 표준)
            return email.utils.parsedate_to_datetime(t).timestamp()
        except (TypeError, ValueError, IndexError):
            pass
        try:  # ISO 8601 (Atom)
            return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return None


def _parse_feed(name: str, url: str, internal_type: str) -> list[dict]:
    resp = requests.get(url, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    # RSS 2.0: rss/channel/item
    items_xml = root.findall(".//item")
    out = []
    for it in items_xml:
        title = _text(it, "title")
        link = _text(it, "link")
        guid = _text(it, "guid") or link
        if not title or not link:
            continue
        desc = _strip_html(_text(it, "description"))
        out.append(
            {
                "id": f"rss:{guid}",
                "source_type": internal_type,
                "source_name": name,
                "title": title,
                "url": link,
                "body": desc[:500],
                "published_at": _parse_date(it),
            }
        )
    return out


def collect() -> list[dict]:
    items: list[dict] = []
    for name, url, internal_type in _FEEDS:
        try:
            fetched = _parse_feed(name, url, internal_type)
            items.extend(fetched)
            print(f"[rss] {name}: {len(fetched)}건 수집")
        except (requests.RequestException, ET.ParseError, ValueError) as exc:
            print(f"[rss] {name} 수집 실패(건너뜀): {exc}")
    return items
