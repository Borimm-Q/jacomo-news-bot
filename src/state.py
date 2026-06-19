"""중복 발송 방지용 상태 저장.

이미 처리(발송 또는 제외 판정)한 항목의 고유 ID를 state/seen.json 에 기록합니다.
GitHub Actions 가 매 실행 후 이 파일을 커밋해 다음 실행에서 중복을 막습니다.

형식: { "<id>": <마지막 확인 epoch초> }
오래된 ID 는 자동 정리해 파일이 무한정 커지지 않게 합니다.
"""
import json
import time

from config import STATE_PATH

# 이 기간(초)보다 오래된 기록은 정리. (14일)
_TTL_SECONDS = 14 * 24 * 60 * 60
# 안전장치: 최대 보관 개수
_MAX_ENTRIES = 5000


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
