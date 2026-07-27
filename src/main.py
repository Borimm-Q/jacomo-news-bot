"""자코모 텔레그램 속보 봇 — 전체 오케스트레이션.

흐름: 소스 수집 → 중복 제거 → (Claude 가공/필터/사건중복제거) → 텔레그램 발행 → 상태 저장
GitHub Actions cron 이 15분마다 이 파일을 실행합니다.
"""
import random
import time

import config
import rewrite
import state
import telegram
from sources import collect_all

# 발행 사이 딜레이(초) — 한꺼번에 다다다 쏟아지는 걸 막는 난수 간격
_DELAY_MIN, _DELAY_MAX = 30, 60

# 이 시간(초) 안에 나온 따끈한 뉴스만 [속보], 그 외엔 [이전 속보]
_FRESH_SECONDS = 10 * 60


def _make_tag(kind: str, published_at: float | None, now: float) -> str:
    """헤더 태그 결정: 분석이면 [분석], 10분 이내 뉴스면 [속보], 그 외엔 [이전 속보]."""
    if kind == "analysis":
        return "📊 [분석]"
    if published_at is not None and (now - published_at) < _FRESH_SECONDS:
        return "🚨 [속보]"
    return "🕐 [이전 속보]"


def run() -> None:
    # 키가 아직 없으면(예: Secrets 등록 전) 에러 없이 조용히 종료
    if not config.is_configured():
        print("[main] 필수 키(Gemini / 텔레그램) 미설정 — 아무 작업 없이 종료합니다. "
              "GitHub Secrets 등록 후 자동 동작합니다.")
        return

    seen = state.load_seen()
    published = state.load_published()
    items = collect_all()
    print(f"[main] 수집 {len(items)}건")

    # 처음 실행(상태 비어 있음)이면 과거 누적분이 한꺼번에 쏟아지는 걸 막기 위해
    # 현재 항목을 모두 '확인함'으로만 기록하고 발행은 하지 않는다.
    if not seen:
        for it in items:
            state.mark(seen, it["id"])
        state.save_seen(seen)
        print(f"[main] 최초 실행: {len(items)}건을 기준선으로 기록(발행 안 함).")
        return

    new_items = [it for it in items if not state.is_seen(seen, it["id"])]
    # 최신순 정렬 — 한꺼번에 많이 떠도 '따끈한 것 먼저' 보낸다. 묵은 건 자연히 밀려 안 나감.
    new_items.sort(key=lambda it: it.get("published_at") or 0.0, reverse=True)
    print(f"[main] 신규 {len(new_items)}건")

    # 밀릴 때 '중요·비중복'이 먼저 나가도록, 후보는 상한의 2배까지 넉넉히 Claude에 넘긴다.
    # (평소엔 신규가 몇 개뿐이라 추가 비용 없음. 버스트 때만 더 넓게 평가)
    candidates = new_items[: config.MAX_POSTS_PER_RUN * 2]

    # 배칭: 한 번의 Claude 호출로 가공(저중요도·중복 제거) + 최근 발행분 대조로 회차 간 중복 차단
    results = rewrite.process_batch(candidates, recent_titles=state.recent_titles(published))
    for it in candidates:
        state.mark(seen, it["id"])  # 발행 여부와 무관하게 재처리 방지

    # 살아남은 것 중 최신순 상위 N건만 발행 (results 는 candidates(최신순) 순서 유지)
    to_post = results[: config.MAX_POSTS_PER_RUN]

    now = time.time()
    posted = 0
    for i, result in enumerate(to_post):
        tag = _make_tag(result.get("kind", "news"), result.get("published_at"), now)
        text = telegram.format_message(
            title_ko=result["title_ko"],
            summary_ko=result["summary_ko"],
            category=result["category"],
            url=result["url"],
            source=result["source_name"],
            tag=tag,
        )
        try:
            telegram.send(text)
            posted += 1
            state.add_published(published, result["title_ko"])  # 발행 이력에 기록
        except RuntimeError as exc:
            print(f"[main] 발송 실패: {exc}")
            continue
        # 마지막 항목 빼고 난수 딜레이 (한꺼번에 쏟아짐 방지). 미리보기(DRY_RUN)는 안 쉼.
        if not config.DRY_RUN and i < len(to_post) - 1:
            time.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))

    state.save_seen(seen)
    state.save_published(published)
    print(f"[main] 완료: {posted}건 발행 (후보 {len(candidates)}건 평가), 신규 {len(new_items)}건")


if __name__ == "__main__":
    run()
