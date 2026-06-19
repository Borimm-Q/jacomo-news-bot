"""속보 소스 수집 패키지.

각 수집 함수는 아래 공통 형태(dict)의 리스트를 반환합니다:
    {
        "id": str,            # 중복 방지용 고유 ID (소스명:원본ID)
        "source_type": str,   # "exchange" | "crypto" | "market"
        "source_name": str,   # 사람이 읽는 출처명 (예: "업비트", "CoinDesk")
        "title": str,         # 원본 제목
        "url": str,           # 원문 링크
        "body": str,          # (선택) 추가 텍스트. 없으면 빈 문자열
    }
어떤 소스가 실패해도 전체가 멈추지 않도록 각 수집기는 예외를 자체 처리하고
빈 리스트를 반환합니다.
"""
from sources import exchanges, market, news, rss


def collect_all() -> list[dict]:
    items: list[dict] = []
    items.extend(exchanges.collect())   # 거래소 공식 공지
    items.extend(rss.collect())         # 코인 매체 RSS (CoinDesk·Cointelegraph·TheBlock·Decrypt·WuBlockchain)
    items.extend(market.collect())      # 시장·매크로·지정학 (Finnhub)
    items.extend(news.collect())        # 코인 뉴스 보강 (CryptoPanic, 선택)
    return items
