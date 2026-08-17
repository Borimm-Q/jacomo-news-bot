# 뉴스 소스 레퍼런스 (자코모 속보봇)

**목적**: 이 문서는 자코모 속보봇이 사용하는 모든 뉴스 소스의 완전한 기술 레퍼런스입니다.
엔드포인트, 인증 방식, 응답 구조, 필드 매핑, 요청 한도, 실제로 겪은 함정과 해결책까지 담았습니다.
**새 뉴스 엔진을 만들 때 이 문서만 보고 바로 구현할 수 있도록** 작성했습니다.

- 정의 위치: `src/sources/` (`exchanges.py`, `rss.py`, `market.py`, `news.py`)
- 실행 주기: 15분 (GitHub Actions + cron-job.org)
- 가공 엔진: 구글 제미나이 무료 티어 (`gemini-flash-latest`) → **API 비용 $0**
- 검증 일자: 2026-08-17 (모든 엔드포인트 실측 확인)

---

## 목차

1. [실측 수집 현황](#1-실측-수집-현황)
2. [공통 데이터 구조](#2-공통-데이터-구조)
3. [거래소 공식 공지 API](#3-거래소-공식-공지-api)
4. [코인 매체 RSS](#4-코인-매체-rss)
5. [Finnhub 시장·매크로 API](#5-finnhub-시장매크로-api)
6. [CryptoPanic (선택)](#6-cryptopanic-선택)
7. [제외한 소스와 사유](#7-제외한-소스와-사유)
8. [실전 함정 모음](#8-실전-함정-모음)
9. [저작권·법적 안전 원칙](#9-저작권법적-안전-원칙)
10. [소스 추가·제거 방법](#10-소스-추가제거-방법)
11. [확장 후보 소스](#11-확장-후보-소스)

---

## 1. 실측 수집 현황

매 회차 **16개 매체에서 약 494건**을 수집합니다. (2026-08-17 1회 실측)

| 매체 | 건수 | 경로 | 성격 |
|---|---:|---|---|
| Cointelegraph | 78 | RSS + Finnhub | 코인 전문 |
| CoinDesk | 73 | RSS + Finnhub | 코인 전문 |
| **Reuters** | 73 | Finnhub | 국제 통신사 |
| 토큰포스트 | 50 | RSS | 국내 코인 |
| **GlobalNewswire** | 45 | Finnhub | 기업 공시·보도자료 |
| Decrypt | 34 | RSS | 코인 전문 |
| **SeekingAlpha** | 21 | Finnhub | 투자 분석 |
| 바이낸스 | 20 | 공식 API | 거래소 공지 |
| OKX | 20 | 공식 API | 거래소 공지 |
| KuCoin | 20 | 공식 API | 거래소 공지 |
| The Block | 20 | RSS | 코인 전문 |
| **CNBC** | 14 | Finnhub | 경제 방송 |
| **Bloomberg** | 13 | Finnhub | 금융 통신사 |
| 블록미디어 | 10 | RSS | 국내 코인 |
| Forexlive | 2 | Finnhub | 외환 |
| BusinessWire | 1 | Finnhub | 보도자료 |
| **합계** | **494** | | |

> **핵심**: Reuters·Bloomberg·CNBC 등 대형 외신은 **개별 계약 없이 Finnhub 무료 API 하나로** 커버됩니다.
> RSS로 직접 구독하는 매체는 6곳이지만, 실제 커버리지는 16개 매체입니다.

**비용 요약**

| 항목 | 비용 |
|---|---|
| 거래소 공지 API (3곳) | 무료 (키 불필요) |
| RSS (6개 매체) | 무료 (키 불필요) |
| Finnhub | 무료 티어 (가입만, 카드 불필요) |
| 제미나이 가공 | 무료 티어 |
| GitHub Actions (퍼블릭 repo) | 무료 무제한 |
| cron-job.org | 무료 |
| **합계** | **$0 / 월** |

---

## 2. 공통 데이터 구조

모든 수집기는 아래 형태의 `dict` 리스트를 반환합니다. 이 규격만 맞추면 소스를 자유롭게 추가할 수 있습니다.

```python
{
    "id":           str,          # 중복 방지용 고유 ID. "소스명:원본ID" 형식 (필수)
    "source_type":  str,          # "exchange" | "crypto" | "market"  (필수)
    "source_name":  str,          # 화면에 표시할 출처명. 예: "바이낸스", "CoinDesk" (필수)
    "title":        str,          # 원본 제목 (필수)
    "url":          str,          # 원문 링크 (필수)
    "body":         str,          # 요약·본문 일부. 없으면 "" (선택)
    "published_at": float | None, # 발행 시각 epoch 초. 신선도 태그 계산용 (선택)
}
```

**설계 원칙**

- **`id`는 소스별 프리픽스 필수** (`binance:`, `rss:`, `finnhub:`) — 서로 다른 소스에서 같은 숫자 ID가 나와도 충돌하지 않습니다.
- **`published_at`은 epoch 초(float)로 통일** — 소스마다 ISO8601, epoch 초, epoch 밀리초로 제각각이므로 수집 단계에서 변환합니다.
- **각 수집기는 예외를 자체 처리하고 빈 리스트를 반환** — 한 소스가 죽어도 나머지는 정상 동작해야 합니다.

```python
def collect() -> list[dict]:
    items = []
    for name, fetcher in _FETCHERS:
        try:
            items.extend(fetcher())
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"[exchange] {name} 수집 실패(건너뜀): {exc}")
    return items
```

---

## 3. 거래소 공식 공지 API

상장·상장폐지·이벤트·점검 등 거래소가 직접 발표하는 **1차 정보**입니다.
사실 그 자체이며 거래소가 확산을 원하는 정보라 **법적으로 가장 안전**합니다.

정의: `src/sources/exchanges.py` → `_FETCHERS`

**공통 요청 헤더** (봇 차단 회피용, 3곳 모두 동일하게 사용)

```python
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
```

### 3-1. 바이낸스 ✅

```
GET https://www.binance.com/bapi/composite/v1/public/cms/article/list/query
    ?type=1&catalogId=48&pageNo=1&pageSize=20
```

- **인증**: 불필요
- **catalogId=48**: 신규 상장(New Cryptocurrency Listing). 다른 카테고리는 ID를 바꾸면 됩니다.
- **응답 경로**: `data.catalogs[].articles[]` (일부 응답은 `data.articles[]`에 옴 → **둘 다 확인 필요**)

**article 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | int | 내부 ID |
| `code` | str | **링크 생성용 해시** (이게 URL에 들어감) |
| `title` | str | 공지 제목 |
| `type` | int | 문서 타입 |
| `releaseDate` | int | **epoch 밀리초** (÷1000 필요) |

**매핑 코드**

```python
url = f"https://www.binance.com/en/support/announcement/{a['code']}"
published_at = float(a["releaseDate"]) / 1000.0   # ms → s
item_id = f"binance:{a['code']}"
```

**실제 응답 예시**

```json
{"id": 282552, "code": "0872245db74c4daaabd4f11984ba52c1",
 "title": "Binance Futures Will Launch Multiple USDⓈ-Margined TradFi Perpetual Contracts",
 "type": 1, "releaseDate": 1786932925476}
```

### 3-2. OKX ✅

```
GET https://www.okx.com/api/v5/support/announcements?page=1
```

- **인증**: 불필요 (공식 v5 API)
- **응답 경로**: `data[].details[]` — **2단 중첩**이라 이중 루프 필요

**details 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `annType` | str | 공지 분류 (`announcements-new-listings` 등) |
| `title` | str | 제목 |
| `url` | str | **완성된 전체 URL** (조합 불필요) |
| `pTime` | str | **epoch 밀리초 (문자열)** |
| `businessPTime` | str | 사업 기준 시각 |

**매핑 코드**

```python
for block in data:                      # data[] 순회
    for n in block.get("details", []):  # details[] 순회 (2단 중첩)
        item_id = f"okx:{n['url']}"     # 고유 ID가 없어 URL을 ID로 사용
        published_at = float(n["pTime"]) / 1000.0
```

### 3-3. KuCoin ✅

```
GET https://api.kucoin.com/api/v3/announcements
    ?currentPage=1&pageSize=20&lang=en_US
```

- **인증**: 불필요 (공식 공개 API)
- **응답 경로**: `data.items[]`
- **장점**: `annDesc`로 **본문 요약까지 제공** (다른 거래소는 제목만)

**items 필드**

| 필드 | 타입 | 설명 |
|---|---|---|
| `annId` | int | 고유 ID |
| `annTitle` | str | 제목 |
| `annType` | list | 분류 배열 (`["latest-announcements"]`) |
| `annDesc` | str | **본문 요약** |
| `language` | str | 언어 |
| `annUrl` | str | 전체 URL |
| `cTime` | int | epoch 밀리초 |

### 3-4. 업비트 ⛔ 비활성화

```
GET https://api-manager.upbit.com/api/v1/announcements
    ?os=web&page=1&per_page=20&category=all
```

- **응답 경로**: `data.notices[]` (필드: `id`, `title`, `listed_at`(ISO8601), `category`)
- **URL 조합**: `https://upbit.com/service_center/notice?id={id}`
- **필수 헤더**: `Referer: https://upbit.com/`

> ⛔ **차단 사유**: GitHub Actions 서버(미국 IP)에서 **403 Forbidden**.
> User-Agent를 브라우저로 위장해도 뚫리지 않습니다. IP 기반 지역/데이터센터 차단으로 판단됩니다.
> 로컬(한국 IP)에서는 정상 동작을 확인했습니다.
>
> **해결책**: 한국 IP 서버(국내 VPS·라즈베리파이 등)에서 실행하면 `_FETCHERS`의 주석만 풀어 즉시 사용 가능합니다.
> 현재는 업비트 상장 소식을 **토큰포스트·블록미디어가 대부분 보도**해 실질적 공백은 크지 않습니다.

### 3-5. 빗썸 ⛔ 제외

`https://feed.bithumb.com/notice` → **403 (Cloudflare 봇 차단)**. 우회는 약관 위반 소지가 있어 시도하지 않았습니다.

---

## 4. 코인 매체 RSS

정의: `src/sources/rss.py` → `_FEEDS`

- **인증**: 전부 불필요
- **형식**: 모두 RSS 2.0 (`<item>` 기반) → 표준 라이브러리 `xml.etree.ElementTree`만으로 파싱 가능 (외부 패키지 불필요)

| 매체 | 지역 | RSS 주소 | 실측 건수 |
|---|---|---|---:|
| CoinDesk | 해외 | `https://www.coindesk.com/arc/outboundfeeds/rss/` | 25 |
| Cointelegraph | 해외 | `https://cointelegraph.com/rss` | 30 |
| The Block | 해외 | `https://www.theblock.co/rss.xml` | 20 |
| Decrypt | 해외 | `https://decrypt.co/feed` | 34 |
| 토큰포스트 | 국내 | `https://www.tokenpost.kr/rss` | 50 |
| 블록미디어 | 국내 | `https://www.blockmedia.co.kr/feed` | 10 |
| Wu Blockchain | ⛔ 제외 | `https://wublock.substack.com/feed` | - |

> ⛔ **Wu Blockchain 제외 사유**: Substack이 GitHub Actions IP를 403 차단합니다.
> 콜린 우(@WuBlockchain)는 아시아 코인 속보의 핵심 소스라 아쉬운 부분으로, 한국 IP 환경이라면 다시 넣을 가치가 큽니다.

**파싱 시 주의점**

```python
_HEADERS = {  # Substack 등이 봇 UA를 막으므로 브라우저로 위장
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/124.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

root = ET.fromstring(resp.content)   # ← resp.text 아님! 인코딩 오류 방지
items = root.findall(".//item")      # 네임스페이스 무시하고 안전하게 탐색

guid = _text(it, "guid") or link     # guid 없는 피드 대비
desc = _TAG_RE.sub("", _text(it, "description"))[:500]  # HTML 태그 제거 + 길이 제한
```

**날짜 파싱** — 피드마다 형식이 달라 2단계로 시도합니다.

```python
for tag in ("pubDate", "published", "updated", "date"):
    t = _text(elem, tag)
    if not t:
        continue
    try:    # RFC822 (RSS 표준): "Mon, 17 Aug 2026 12:00:00 +0900"
        return email.utils.parsedate_to_datetime(t).timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    try:    # ISO 8601 (Atom): "2026-08-17T12:00:00Z"
        return datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
    except ValueError:
        pass
return None
```

실측 결과 위 6개 피드는 **171건 전부 발행 시각 파싱 성공**(100%)했습니다.

---

## 5. Finnhub 시장·매크로 API

**이 문서에서 가장 중요한 소스입니다.** 하나의 무료 API로 Reuters·Bloomberg·CNBC 등
대형 외신 헤드라인을 개별 계약 없이 커버합니다. 매 회차 **약 265건**이 이 경로로 들어옵니다.

정의: `src/sources/market.py`

```
GET https://finnhub.io/api/v1/news?category={category}&token={API_KEY}
```

- **키 발급**: https://finnhub.io — 이메일 가입만, **신용카드 불필요**
- **무료 한도**: 분당 60회 (15분에 4회 호출하는 우리 사용량은 한도의 1% 수준)
- **응답**: JSON 배열 (객체 아님, 바로 `[...]`)

### 수집 카테고리

| category | 내부 분류 | 실측 건수 | 내용 |
|---|---|---:|---|
| `general` | market | 100 | 일반 경제·지정학·정책 |
| `forex` | market | 1 | 환율 |
| `merger` | market | 67 | M&A |
| `crypto` | crypto | 97 | 코인 |

### 포함되는 매체 (실측)

Reuters(73) · GlobalNewswire(45) · SeekingAlpha(21) · CNBC(14) · Bloomberg(13) · Forexlive(2) · BusinessWire(1)
+ Cointelegraph·CoinDesk 등 코인 매체(crypto 카테고리)

### 응답 필드

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | int | 고유 ID |
| `category` | str | 분류 (`top news` 등) |
| `datetime` | int | **epoch 초** (밀리초 아님 — ÷1000 하지 말 것) |
| `headline` | str | 제목 |
| `summary` | str | **요약문** (가공 품질에 크게 기여) |
| `source` | str | 매체명 (`Reuters`, `Bloomberg` 등) |
| `url` | str | 원문 링크 |
| `image` | str | 이미지 URL (**저작권 문제로 사용 안 함**) |
| `related` | str | 관련 티커 |

**매핑 코드**

```python
{
    "id": f"finnhub:{a['id']}",
    "source_type": internal_type,        # general/forex/merger → "market", crypto → "crypto"
    "source_name": a.get("source") or "시장 뉴스",   # ← Reuters, Bloomberg 등이 여기서 나옴
    "title": a["headline"],
    "url": a["url"],
    "body": (a.get("summary") or "").strip(),
    "published_at": float(a["datetime"]),   # epoch 초 그대로 (÷1000 금지)
}
```

> ⚠️ **카테고리 간 중복 주의**: 같은 기사가 `general`과 `crypto`에 동시에 나올 수 있습니다.
> 카테고리 루프를 돌 때 `seen_ids` 집합으로 걸러야 합니다.

---

## 6. CryptoPanic (선택)

```
GET https://cryptopanic.com/api/v1/posts/?auth_token={TOKEN}&public=true&kind=news
```

- 정의: `src/sources/news.py`
- **현재 미사용** — `CRYPTOPANIC_TOKEN`이 없으면 자동으로 건너뜁니다.
- 여러 매체 기사를 **제목+출처+링크만** 모아 제공 (본문 없음 → 저작권 안전)
- 응답: `results[]` (필드: `id`, `title`, `url`, `source.title`, `published_at`(ISO8601))
- Finnhub와 커버리지가 겹쳐 현재는 활성화하지 않았습니다.

---

## 7. 제외한 소스와 사유

| 소스 | 사유 | 재개 가능성 |
|---|---|---|
| **코인니스 (Coinness)** | 공식 RSS가 없고 **내부 API(`api.coinness.com/feed/v1/news`)만 존재**. 300여 매체를 큐레이션해 파는 **상업 서비스**라 무단 수집 시 이용약관 위반·무임승차 리스크. | ❌ 정식 제휴 시에만 |
| **특파원 김씨 등 유료 속보 채널** | 그들의 `AI+` 해석·논평·시장 브리핑은 **창작물이라 저작권 보호 대상**. 유료 구독 상품(월 30 USDT)이라 재발행 시 분쟁 소지. | ❌ |
| 업비트 | GitHub Actions IP 403 차단 | ✅ 한국 IP 서버면 즉시 |
| Wu Blockchain | Substack IP 403 차단 | ✅ 한국 IP 서버면 즉시 |
| 빗썸 | Cloudflare 봇 차단 | ⚠️ 공식 API 확인 필요 |

> **중요한 판단 기준**: 특파원 김씨 채널 3년치(281,835건)를 분석한 결과, 그들의 출처 1위는
> **@WuBlockchain(14,285건)**, 그 외 CoinDesk·The Block·Cointelegraph·거래소 공지였습니다.
> 즉 **유료 채널을 베끼지 않고 그들이 인용하는 원천 매체를 직접 구독하면 커버리지의 약 80%를 합법적으로 확보**할 수 있습니다.
> 나머지 20%(X 실시간 스트림, 블룸버그 터미널급 와이어)가 유료 채널의 진짜 해자입니다.

---

## 8. 실전 함정 모음

새 엔진을 만들 때 똑같이 겪을 문제들입니다. 전부 실제로 부딪히고 해결한 것입니다.

### 8-1. GitHub Actions IP 차단
업비트·Substack이 데이터센터 IP를 403으로 막습니다. **User-Agent 위장으로는 해결되지 않습니다.**
→ 한국 IP 서버가 필요하거나, 해당 소스를 포기하고 대체 매체로 커버해야 합니다.

### 8-2. 시각 단위 불일치
| 소스 | 단위 | 변환 |
|---|---|---|
| Finnhub `datetime` | **epoch 초** | 그대로 |
| 바이낸스 `releaseDate` | epoch 밀리초 | ÷ 1000 |
| OKX `pTime` | epoch 밀리초 (문자열) | `float()` 후 ÷ 1000 |
| KuCoin `cTime` | epoch 밀리초 | ÷ 1000 |
| 업비트 `listed_at` | ISO 8601 | `datetime.fromisoformat` |
| RSS `pubDate` | RFC 822 | `email.utils.parsedate_to_datetime` |

**Finnhub만 초 단위**라 습관적으로 ÷1000 하면 1970년으로 날아갑니다.

### 8-3. 텔레그램 HTML 이스케이프
Python `html.escape(s, quote=True)`는 작은따옴표를 `&#x27;`로 바꾸는데,
**텔레그램은 이를 엔티티로 해석하지 않아 화면에 `&#x27;`가 그대로 보입니다.**

```python
def _esc(s: str) -> str:   # 텔레그램이 처리하는 & < > 만 변환
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
```

### 8-4. 제미나이 thinking 토큰
`gemini-flash-latest`는 **내부 thinking 토큰도 `maxOutputTokens`에서 차감**해
한도가 빠듯하면 JSON이 중간에 잘려 파싱에 실패합니다. (실측: thinking에 227토큰 소모)

- `thinkingConfig.thinkingBudget: 0`으로 끄려 하면 **HTTP 400 (INVALID_ARGUMENT)** — 이 모델은 거부합니다.
- **해결**: 필요량보다 넉넉히 배정. 배치는 `min(700 * 건수 + 1000, 16000)`.
- 인증은 `X-goog-api-key` **헤더** 방식 사용 (`AQ.` 형식 키 대응).

### 8-5. 포럼 그룹 토픽 발행
텔레그램 포럼(주제별) 그룹의 특정 토픽에만 쏘려면 `sendMessage`에 `message_thread_id`가 필요합니다.
없으면 본방 전체에 도배됩니다.

```python
payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
if THREAD_ID:
    payload["message_thread_id"] = int(THREAD_ID)
```

토픽 ID는 링크 `t.me/{group}/{topic_id}` 의 숫자이거나, 봇을 추가한 뒤 `getUpdates`의
`forum_topic_created` 이벤트에서 확인할 수 있습니다.

### 8-6. GitHub 자체 cron의 신뢰성
`schedule: cron` 은 정시(:00, :15)에 부하가 몰리면 **지연되거나 그냥 건너뜁니다.**
실측에서 30분간 단 한 번도 실행되지 않았습니다.

- 완화책: 정시를 피한 분 지정 (`4,19,34,49 * * * *`)
- **근본 해결**: 외부 스케줄러(cron-job.org 무료)가 `workflow_dispatch` API로 깨우기

```
POST https://api.github.com/repos/{owner}/{repo}/actions/workflows/{file}/dispatches
Headers: Accept: application/vnd.github+json
         Authorization: Bearer {fine-grained PAT, Actions:read+write}
         X-GitHub-Api-Version: 2022-11-28
Body: {"ref": "main"}
→ 204 No Content = 성공
```

### 8-7. 첫 실행 폭탄 방지
상태 파일(`seen.json`)이 비어 있으면 수집한 500건이 한꺼번에 발행됩니다.
**최초 실행은 전량을 "확인함"으로만 기록하고 발행하지 않도록** 처리해야 합니다.

---

## 9. 저작권·법적 안전 원칙

**근거**: 한국 저작권법 제7조 5호 — "사실의 전달에 불과한 시사보도"는 저작권 보호 대상이 아닙니다.
즉 **사실(누가/무엇을/언제/수치)은 자유롭게 쓸 수 있으나, 기사의 문장·표현·사진·독창적 분석은 보호**됩니다.

봇이 코드와 프롬프트로 강제하는 5원칙:

1. **공식 1차 출처 우선** — 거래소 공지, 공식 RSS, 공개 API만 사용
2. **원문 문장 복제 금지** — 사실만 추출해 전부 새 문장으로 재작성 (한국어 기사도 동일)
3. **출처 링크 항상 표기** — 매체명 + "원문 보기" 링크
4. **이미지 미사용** — Finnhub가 `image` 필드를 주지만 사용하지 않음
5. **해석·전망 배제** — 사실 보도에 우리 해석을 붙이지 않음 (분석 기사는 `[분석]` 태그로 명시 구분)

추가로 채널에 면책 문구를 고정할 것을 권장합니다.
> 본 채널은 공개된 정보를 요약·정리해 전달하며, 각 속보에 원문 링크를 제공합니다. 투자 판단과 책임은 본인에게 있습니다.

---

## 10. 소스 추가·제거 방법

**RSS 매체 추가** — `src/sources/rss.py`의 `_FEEDS`에 한 줄:

```python
_FEEDS = [
    ...
    ("매체명", "https://example.com/rss", "crypto"),   # (표시명, 주소, 분류)
]
```

**거래소 추가** — `src/sources/exchanges.py`에 함수를 만들고 `_FETCHERS`에 등록:

```python
def _newexchange() -> list[dict]:
    resp = requests.get(URL, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    return [{...공통 규격...} for n in resp.json()["data"]]

_FETCHERS = [..., ("거래소명", _newexchange)]
```

**일시 중단** — 해당 줄을 `#`으로 주석 처리. 다른 소스는 영향받지 않습니다.

**추가 시 체크리스트**

- [ ] `id`에 소스 프리픽스를 붙였는가
- [ ] `published_at`을 epoch **초**로 변환했는가 (밀리초/ISO 주의)
- [ ] 예외를 자체 처리해 빈 리스트를 반환하는가
- [ ] 로컬에서 되는데 클라우드에서 403이 아닌지 확인했는가

---

## 11. 확장 후보 소스

현재는 쓰지 않지만 뉴스 엔진 확장 시 검토할 만한 소스입니다.

| 소스 | 성격 | 비용 | 비고 |
|---|---|---|---|
| **X(트위터) API** | 실시간 속보 | 유료 (Basic $200/월~) | 유료 속보 채널의 진짜 해자. WuBlockchain·KobeissiLetter 등 실시간 추적용 |
| **NewsData.io** | 다국어 뉴스 | 무료 티어 있음 | 한국어 포함 다국어 커버 |
| **CoinGecko News API** | 코인 뉴스 | 무료 티어 | 30개 이상 언어 로케일 지원 |
| **거래소 WebSocket** | 상장 즉시 감지 | 무료 | 공지보다 빠를 수 있음 |
| **SEC EDGAR** | 미국 기업 공시 | 무료 | 상장사 공시 원문 |
| **한국은행 / 금융위 RSS** | 국내 정책 | 무료 | 국내 규제 이슈 |
| 디센터 / 코인데스크코리아 | 국내 코인 | 무료 | ⚠️ 실측 시 RSS 응답 0건 (확인 필요) |

**우선순위 제안**

1. 한국 IP 서버 확보 → 업비트 + Wu Blockchain 즉시 복구 (무료, 커버리지 개선 폭 큼)
2. 국내 정책·규제 RSS 추가 (무료, 한국 독자에게 가치 높음)
3. X API는 예산이 확보될 때만 (실시간성이 필요한 경우)
