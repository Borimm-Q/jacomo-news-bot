# 자코모 텔레그램 속보 봇

자두두 코인 모임(자코모) 텔레그램 커뮤니티의 **속보 채널**에, 봇이 코인 소식을
**합법적이고 안전하게** 가공해 자동으로 올려주는 시스템입니다.

- **소스**:
  - ① 거래소 공식 공지 (업비트·바이낸스)
  - ② 코인 매체 RSS (CoinDesk·Cointelegraph·The Block·Decrypt·Wu Blockchain)
  - ③ 시장·매크로·지정학 뉴스 (Finnhub: general·forex·crypto·merger)
  - ④ 코인 뉴스 보강 (CryptoPanic, 선택)
- **가공**: Claude(Haiku)가 사실만 추출해 한국어 친절체로 새로 작성 + 분류/필터
- **발행**: 텔레그램 봇이 채널에 자동 게시 (완전 자동)
- **구동**: GitHub Actions cron (5분마다, 무료)

> 코인뿐 아니라 매크로 경제·금리/환율/유가·지정학·주요 기업/규제 소식까지 다룹니다.
> 단순 가격 급등락(시세·자금이동) 알림과 자두두 관련 내용, 광고는 발행하지 않습니다.
> 해석·전망 없이 '사실 요약'만 전달합니다.

---

## 왜 합법인가 (저작권)

한국 저작권법 제7조 5호는 **"사실의 전달에 불과한 시사보도"는 저작권 보호 대상이 아님**을
규정합니다. 그래서 이 봇은:

1. 거래소 **공식 공지**(1차 출처)를 우선 사용하고,
2. 기사의 **문장을 복제하지 않고 사실만 추출해 우리 문장으로 새로 쓰며**,
3. 항상 **출처 링크**를 답니다.
4. 기사 **사진·차트는 사용하지 않습니다.**
5. 채널에 **면책 문구**를 고정해 둡니다.

---

## 폴더 구조

```
├── .github/workflows/news.yml   # 5분마다 자동 실행
├── src/
│   ├── main.py                  # 전체 흐름
│   ├── config.py                # 환경변수/설정
│   ├── state.py                 # 중복 발송 방지(seen.json)
│   ├── telegram.py              # 채널 발행
│   ├── rewrite.py               # Claude 가공/필터
│   └── sources/
│       ├── exchanges.py         # 거래소 공식 공지 (업비트·바이낸스)
│       ├── rss.py               # 코인 매체 RSS (CoinDesk·Cointelegraph·TheBlock·Decrypt·WuBlockchain)
│       ├── market.py            # 시장·매크로·지정학 뉴스 (Finnhub)
│       └── news.py              # 코인 뉴스 보강 (CryptoPanic, 선택)
├── state/seen.json              # 발송 기록 (자동 갱신)
├── requirements.txt
└── .env.example                 # 로컬 테스트용 환경변수 예시
```

---

## 준비물 (한 번만 세팅)

1. **텔레그램 봇 만들기** — 텔레그램에서 `@BotFather` 검색 → `/newbot` → 토큰 받기.
2. **속보 채널 만들기** → 봇을 그 채널의 **관리자**로 추가.
   - 채널 ID 확인: 공개 채널이면 `@채널아이디`, 비공개면 `-100`으로 시작하는 숫자 ID.
     (숫자 ID는 봇을 추가한 뒤 `https://api.telegram.org/bot<토큰>/getUpdates` 로 확인 가능)
3. **Anthropic(Claude) API 키** — console.anthropic.com 에서 발급.
4. **Finnhub API 키** — https://finnhub.io/ 무료 가입 후 발급 (시장·매크로 뉴스용, 핵심).
5. **CryptoPanic 토큰** (선택) — https://cryptopanic.com/developers/api/ 에서 무료 발급.

---

## 로컬 테스트 (실제로 올리기 전 확인)

```bash
pip install -r requirements.txt
cp .env.example .env      # 그리고 .env 에 값 채우기
# 먼저 DRY_RUN=1 로 두면 텔레그램에 안 보내고 콘솔에 미리보기만 출력됩니다.
python src/main.py
```

- 미리보기가 잘 나오면 `.env` 에서 `DRY_RUN=0` 으로 바꾸고, **비공개 테스트 채널**에
  먼저 실제 발송을 확인하세요.
- ⚠️ `state/seen.json` 이 비어 있으면 **첫 실행은 발행하지 않고** 현재 소식을 '기준선'으로만
  기록합니다(과거 누적분 폭탄 방지). 두 번째 실행부터 새 소식만 발행됩니다.

---

## 클라우드 배포 (GitHub Actions, 무료 상시)

1. 이 폴더를 **새 GitHub 저장소**에 올립니다. (⚠️ 캐시마인 프로덕션 저장소와 분리)
   - Actions 무료 시간 무제한을 위해 **Public 저장소**를 권장합니다.
     비밀값은 코드가 아니라 Secrets 에 저장하므로 공개되어도 안전합니다.
2. 저장소 → **Settings → Secrets and variables → Actions** 에서 아래 항목 등록:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHANNEL_ID` (그룹/채널 ID, 예: `-1002482804660`)
   - `TELEGRAM_THREAD_ID` (선택 — 포럼 그룹의 특정 토픽에만 쏠 때, 예: `234566`)
   - `ANTHROPIC_API_KEY`
   - `FINNHUB_TOKEN`
   - `CRYPTOPANIC_TOKEN` (선택 — 없으면 코인 뉴스 보강만 생략)
3. **Actions** 탭 → `자코모 속보 봇` → **Run workflow** 로 수동 1회 실행해 동작 확인.
4. 이후 5분마다 자동 실행됩니다.

---

## 거래소 엔드포인트 점검

`src/sources/exchanges.py` 의 업비트/바이낸스 공지 API 는 비공식이라 응답 구조가
바뀔 수 있습니다. 수집이 0건이거나 실패 로그가 보이면 해당 거래소 함수를 점검하거나
`_FETCHERS` 목록에서 잠시 주석 처리하세요. (뉴스 소스만으로도 채널은 계속 돌아갑니다.)

---

## 운영 팁

- 발행량이 너무 많으면 워크플로의 `MAX_POSTS_PER_RUN` 을 줄이세요.
- 톤이나 필터를 바꾸려면 `src/rewrite.py` 의 시스템 프롬프트를 수정하세요.
- 채널 고정 메시지(면책 문구) 예시:
  > 본 채널은 공개된 정보를 요약·정리해 전달합니다. 투자 판단과 책임은 본인에게 있습니다.
