"""환경변수 설정을 한 곳에서 읽어옵니다.

로컬에서는 같은 폴더의 .env 파일을, 클라우드(GitHub Actions)에서는
환경변수(=GitHub Secrets)를 사용합니다.
"""
import os
from pathlib import Path

# 프로젝트 루트 (이 파일의 상위의 상위)
ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "seen.json"            # 처리한 항목 ID (소스별 중복 방지)
PUBLISHED_PATH = ROOT / "state" / "published.json"   # 최근 발행한 속보 제목 (사건 중복 방지)


def _load_dotenv() -> None:
    """별도 라이브러리 없이 .env 파일을 직접 읽어 os.environ 에 채워 넣습니다.

    이미 환경변수가 설정돼 있으면(클라우드) 덮어쓰지 않습니다.
    """
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def get(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"환경변수 {name} 가 설정되지 않았습니다. .env 또는 GitHub Secrets 를 확인하세요."
        )
    return value


# 자주 쓰는 값들
TELEGRAM_BOT_TOKEN = lambda: get("TELEGRAM_BOT_TOKEN", required=True)  # noqa: E731
TELEGRAM_CHANNEL_ID = lambda: get("TELEGRAM_CHANNEL_ID", required=True)  # noqa: E731
# 포럼(주제별) 그룹의 특정 토픽에만 쏠 때 사용. 일반 채널이면 비워둠.
TELEGRAM_THREAD_ID = lambda: get("TELEGRAM_THREAD_ID", default="")  # noqa: E731
ANTHROPIC_API_KEY = lambda: get("ANTHROPIC_API_KEY", required=True)  # noqa: E731
CRYPTOPANIC_TOKEN = lambda: get("CRYPTOPANIC_TOKEN", default="")  # noqa: E731
FINNHUB_TOKEN = lambda: get("FINNHUB_TOKEN", default="")  # noqa: E731

MAX_POSTS_PER_RUN = int(get("MAX_POSTS_PER_RUN", default="10") or "10")
DRY_RUN = (get("DRY_RUN", default="0") or "0") == "1"

# Claude 모델: 단순 요약·번역 작업이므로 빠르고 저렴한 Haiku 사용
CLAUDE_MODEL = "claude-haiku-4-5"


def is_configured() -> bool:
    """봇이 실제로 동작하는 데 필요한 키가 모두 있는지 확인.

    키를 아직 등록하지 않은 상태에서 스케줄이 돌더라도 에러 대신 조용히 종료하도록,
    main 에서 이 함수로 먼저 점검한다.
    - 항상 필요: ANTHROPIC_API_KEY
    - 실제 발송(DRY_RUN 아님) 시 추가로 필요: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
    """
    if not get("ANTHROPIC_API_KEY"):
        return False
    if not DRY_RUN and not (get("TELEGRAM_BOT_TOKEN") and get("TELEGRAM_CHANNEL_ID")):
        return False
    return True
