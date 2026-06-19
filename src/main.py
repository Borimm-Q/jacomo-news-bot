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
        print("[main] 필수 키(Anthropic / 텔레그램) 미설정 — 아무 작업 없이 종료합니다. "
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
    print(f"[main] 신규 {len(new_items)}건")

    # 한 번에 너무 많이 보내지 않도록 제한. 남은 건 다음 실행에서 처리.
    to_process = new_items[: config.MAX_POSTS_PER_RUN]

    # 배칭: 여러 건을 한 번의 Claude 호출로 가공(비용 절감)
    # + 최근 발행 목록을 넘겨 회차 간 '같은 사건' 중복을 거른다.
    results = rewrite.process_batch(to_process, recent_titles=state.recent_titles(published))
    for it in to_process:
        state.mark(seen, it["id"])  # 발행 여부와 무관하게 재처리 방지

    now = time.time()
    posted = 0
    for i, result in enumerate(results):
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
        if not config.DRY_RUN and i < len(results) - 1:
            time.sleep(random.uniform(_DELAY_MIN, _DELAY_MAX))

    state.save_seen(seen)
    state.save_published(published)
    print(f"[main] 완료: {posted}건 발행, {len(new_items) - len(to_process)}건 다음 실행 대기")


if __name__ == "__main__":
    run()
