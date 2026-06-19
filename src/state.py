"""중복 발송 방지용 상태 저장.

이미 처리(발송 또는 제외 판정)한 항목의 고유 ID를 state/seen.json 에 기록합니다.
GitHub Actions 가 매 실행 후 이 파일을 커밋해 다음 실행에서 중복을 막습니다.

형식: { "<id>": <마지막 확인 epoch초> }
오래된 ID 는 자동 정리해 파일이 무한정 커지지 않게 합니다.
"""
import json
import time

from config import PUBLISHED_PATH, STATE_PATH

# 이 기간(초)보다 오래된 기록은 정리. (14일)
_TTL_SECONDS = 14 * 24 * 60 * 60
# 안전장치: 최대 보관 개수
_MAX_ENTRIES = 5000

# 발행 이력(사건 중복 방지)은 더 짧게 본다. (48시간)
_PUB_TTL_SECONDS = 48 * 60 * 60
_PUB_MAX_ENTRIES = 80


def load_seen() -> dict[str, float]:
    if not STATE_PATH.exists():
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def is_seen(seen: dict[str, float], item_id: str) -> bool:
    return item_id in seen


def mark(seen: dict[str, float], item_id: str) -> None:
    seen[item_id] = time.time()


def save_seen(seen: dict[str, float]) -> None:
    now = time.time()
    # TTL 지난 항목 제거
    pruned = {k: v for k, v in seen.items() if now - v <= _TTL_SECONDS}
    # 그래도 너무 많으면 최신순으로 자르기
    if len(pruned) > _MAX_ENTRIES:
        newest = sorted(pruned.items(), key=lambda kv: kv[1], reverse=True)
        pruned = dict(newest[:_MAX_ENTRIES])
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(pruned, ensure_ascii=False, indent=0), encoding="utf-8"
    )


# ---- 발행 이력 (사건 중복 방지) -------------------------------------------
# 형식: { "<발행한 한국어 제목>": <발행 epoch초> }
# 최근 48시간 발행분을 Claude 에게 보여줘서 "같은 사건"이면 거르게 한다.

def load_published() -> dict[str, float]:
    if not PUBLISHED_PATH.exists():
        return {}
    try:
        data = json.loads(PUBLISHED_PATH.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def recent_titles(published: dict[str, float]) -> list[str]:
    """최근 발행 제목을 최신순으로 반환(Claude 중복판정용)."""
    return [t for t, _ in sorted(published.items(), key=lambda kv: kv[1], reverse=True)]


def add_published(published: dict[str, float], title: str) -> None:
    published[title] = time.time()


def save_published(published: dict[str, float]) -> None:
    now = time.time()
    pruned = {k: v for k, v in published.items() if now - v <= _PUB_TTL_SECONDS}
    if len(pruned) > _PUB_MAX_ENTRIES:
        newest = sorted(pruned.items(), key=lambda kv: kv[1], reverse=True)
        pruned = dict(newest[:_PUB_MAX_ENTRIES])
    PUBLISHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHED_PATH.write_text(
        json.dumps(pruned, ensure_ascii=False, indent=0), encoding="utf-8"
    )
