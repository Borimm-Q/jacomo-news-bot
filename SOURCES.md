# 뉴스 소스 목록 (자코모 속보봇)

봇이 15분마다 수집하는 전체 소스와 각 엔드포인트를 정리한 문서입니다.
매 회차마다 **16개 매체에서 약 500건**을 수집한 뒤, 중복 제거·중요도 필터를 거쳐 최대 8건만 발행합니다.

## 실측 수집 현황 (1회 기준, 2026-08-17)

| 매체 | 건수 | 경로 |
|---|---:|---|
| Cointelegraph | 78 | RSS + Finnhub |
| CoinDesk | 73 | RSS + Finnhub |
| **Reuters** | 73 | Finnhub |
| 토큰포스트 | 50 | RSS |
| **GlobalNewswire** | 45 | Finnhub |
| Decrypt | 34 | RSS |
| **SeekingAlpha** | 21 | Finnhub |
| 바이낸스 | 20 | 공식 공지 API |
| OKX | 20 | 공식 공지 API |
| KuCoin | 20 | 공식 공지 API |
| The Block | 20 | RSS |
| **CNBC** | 14 | Finnhub |
| **Bloomberg** | 13 | Finnhub |
| 블록미디어 | 10 | RSS |
| Forexlive | 2 | Finnhub |
| BusinessWire | 1 | Finnhub |
| **합계** | **494** | |

> Reuters·Bloomberg·CNBC 등 주요 외신은 개별 계약 없이 **Finnhub 무료 API를 통해** 헤드라인이 들어옵니다.
> (아래 3번 항목) 즉 실제 커버리지는 RSS 목록보다 훨씬 넓습니다.

- 정의 위치: `src/sources/` (`exchanges.py`, `rss.py`, `market.py`, `news.py`)
- 가공 엔진: **구글 제미나이(Gemini) 무료 티어** → API 비용 $0
- 발행 위치: 자코모 본방(`@jadoogroup`)의 "뉴스, 속보" 토픽

---

## 1. 거래소 공식 공지

상장·이벤트·점검 등 거래소가 직접 발표한 1차 정보. 가장 신뢰도가 높습니다.
정의: `src/sources/exchanges.py` → `_FETCHERS`

| 거래소 | 상태 | 엔드포인트 |
|---|---|---|
| 바이낸스 | ✅ 사용 중 | `https://www.binance.com/bapi/composite/v1/public/cms/article/list/query` |
| OKX | ✅ 사용 중 | `https://www.okx.com/api/v5/support/announcements` |
| KuCoin | ✅ 사용 중 | `https://api.kucoin.com/api/v3/announcements` |
| 업비트 | ⛔ 비활성화 | `https://api-manager.upbit.com/api/v1/announcements` |
| 빗썸 | ⛔ 제외 | (Cloudflare 차단) |

> **업비트가 빠진 이유**: 봇이 도는 GitHub Actions 서버(해외 IP)를 업비트가 403으로 차단합니다.
> 코드는 `_upbit()` 함수로 남겨뒀으니, **한국 IP 서버에서 돌리면 주석만 풀어 바로 사용 가능**합니다.
> 업비트 상장 소식은 아래 국내 매체(토큰포스트·블록미디어)가 대부분 보도해 실질적 공백은 적습니다.

---

## 2. 코인 전문 매체 (공식 RSS)

정의: `src/sources/rss.py` → `_FEEDS`

| 매체 | 지역 | RSS 주소 |
|---|---|---|
| CoinDesk | 해외 | `https://www.coindesk.com/arc/outboundfeeds/rss/` |
| Cointelegraph | 해외 | `https://cointelegraph.com/rss` |
| The Block | 해외 | `https://www.theblock.co/rss.xml` |
| Decrypt | 해외 | `https://decrypt.co/feed` |
| 토큰포스트 | 국내 | `https://www.tokenpost.kr/rss` |
| 블록미디어 | 국내 | `https://www.blockmedia.co.kr/feed` |
| Wu Blockchain | ⛔ 제외 | `https://wublock.substack.com/feed` (Substack이 서버 IP 차단) |

---

## 3. 매크로·시장 뉴스 (Finnhub API)

코인 밖의 시장 전반. 무료 API 키 사용.
정의: `src/sources/market.py` → `_CATEGORIES` / 엔드포인트 `https://finnhub.io/api/v1/news`

| 카테고리 | 내용 |
|---|---|
| `general` | 일반 경제·지정학·정책 |
| `forex` | 환율 |
| `merger` | M&A |
| `crypto` | 코인 |

**이 경로 하나로 매 회차 약 265건**이 들어오며, 실측 기준 아래 매체가 포함됩니다.

- **Reuters** (73건) — 국제 통신사
- **GlobalNewswire** (45건) — 기업 공시·보도자료
- **SeekingAlpha** (21건) — 투자 분석
- **CNBC** (14건) — 경제 방송
- **Bloomberg** (13건) — 금융 통신사
- Forexlive, BusinessWire 등

> 즉 Reuters·Bloomberg 같은 대형 외신도 **개별 계약 없이 무료로** 커버됩니다.
> Finnhub가 매체별 헤드라인·요약·링크를 취합해 제공하며, 본문 전문은 받지 않습니다(저작권 안전).

---

## 4. 코인 뉴스 보강 (CryptoPanic, 선택)

정의: `src/sources/news.py` / 엔드포인트 `https://cryptopanic.com/api/v1/posts/`
`CRYPTOPANIC_TOKEN`을 설정하면 활성화되며, 없으면 자동으로 건너뜁니다. **현재 미사용.**

---

## 5. 의도적으로 쓰지 않는 소스

| 소스 | 제외 사유 |
|---|---|
| **코인니스(Coinness)** | 공식 RSS가 없고 내부 API만 존재. 상업 큐레이션 서비스라 무단 수집 시 이용약관 위반·무임승차 리스크. |
| **특파원 김씨 등 유료 속보 채널** | 그들의 해석·논평은 창작물이라 저작권 보호 대상. 대신 그들이 인용하는 **원천 매체를 우리가 직접 구독**하는 방식으로 대체. |
| 빗썸 / Wu Blockchain / 업비트 | 기술적 차단(위 표 참고) |

---

## 6. 저작권·법적 안전 원칙

한국 저작권법 제7조 5호는 **"사실의 전달에 불과한 시사보도"를 저작권 비보호 대상**으로 규정합니다.
이에 따라 봇은 아래 원칙을 코드와 프롬프트로 강제합니다.

1. **공식 1차 출처 우선** (거래소 공지, 공식 RSS, 공개 API만 사용)
2. **원문 문장 복제 금지** — 사실만 추출해 전부 새 문장으로 재작성
3. **출처 링크 항상 표기** (매체명 + 원문 보기)
4. **이미지 미사용** (기사 사진·차트 사용 안 함)
5. **해석·전망 배제** — 사실 보도에는 우리 해석을 붙이지 않음 (분석 기사는 `[분석]` 태그로 구분)

---

## 7. 소스 추가·제거 방법

- **RSS 매체 추가**: `src/sources/rss.py`의 `_FEEDS`에 `("매체명", "RSS주소", "crypto")` 한 줄 추가
- **거래소 추가**: `src/sources/exchanges.py`에 수집 함수를 만들고 `_FETCHERS`에 등록
- **소스 일시 중단**: 해당 줄을 `#`으로 주석 처리 (다른 소스는 그대로 동작)

각 수집기는 실패해도 예외를 자체 처리하므로, **한 소스가 죽어도 전체는 계속 동작**합니다.
