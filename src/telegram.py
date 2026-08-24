"""텔레그램 채널 발행 모듈."""
import time

import requests

import config

_API = "https://api.telegram.org/bot{token}/sendMessage"

# 텔레그램 메시지 길이 상한. 넘기면 API 가 거부하므로 본문을 잘라서 맞춘다.
_TG_MAX_CHARS = 4096

# 카테고리별 표기
_CATEGORY_LABEL = {
    "exchange": "거래소 공지",
    "crypto": "코인",
    "market": "시장·경제",
}


def _esc(s: str) -> str:
    """텔레그램 HTML 모드용 최소 이스케이프.

    텔레그램은 & < > 만 엔티티로 처리하므로 이 셋만 바꾼다.
    (Python html.escape 처럼 따옴표까지 &#x27; 로 바꾸면 텔레그램에선 글자 그대로 보임)
    """
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_message(title_ko: str, summary_ko: str, category: str, url: str,
                   source: str = "", tag: str = "🚨 [속보]") -> str:
    """발행 메시지 본문(HTML)을 만듭니다.

    tag: 헤더 태그. 신선도/종류에 따라 "🚨 [속보]" / "🕐 [이전 속보]" / "📊 [분석]" 중 하나.
    """
    label = _CATEGORY_LABEL.get(category, "속보")
    title_ko = _esc(title_ko.strip())
    summary_ko = _esc(summary_ko.strip())
    src_txt = f" · {_esc(source)}" if source else ""

    def build(summary: str) -> str:
        lines = [
            f"{tag} <b>{title_ko}</b>",
            "",
            summary,
            "",
            f"🏷️ {label}{src_txt}",
        ]
        if url:
            lines.append(f'🔗 <a href="{_esc(url)}">원문 보기</a>')
        return "\n".join(lines)

    text = build(summary_ko)
    if len(text) > _TG_MAX_CHARS:
        # 제목·출처·링크는 그대로 두고 요약만 줄인다. 요약은 태그 없는 평문이라
        # 중간에서 잘라도 HTML 이 깨지지 않는다.
        over = len(text) - _TG_MAX_CHARS + 1
        keep = max(0, len(summary_ko) - over)
        text = build(summary_ko[:keep].rstrip() + "…")
    return text


def send(text: str) -> dict:
    """채널에 메시지를 보냅니다. DRY_RUN 이면 콘솔에만 출력합니다."""
    if config.DRY_RUN:
        print("----- [DRY_RUN] 발송하지 않고 미리보기 -----")
        print(text)
        print("------------------------------------------")
        return {"ok": True, "dry_run": True}

    payload = {
        "chat_id": config.TELEGRAM_CHANNEL_ID(),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    # 포럼 토픽 지정(있을 때만) — 그 토픽 안에만 발행되고 본방 다른 곳엔 안 감
    thread = config.TELEGRAM_THREAD_ID()
    if thread:
        payload["message_thread_id"] = int(thread)

    url = _API.format(token=config.TELEGRAM_BOT_TOKEN())

    def post() -> dict:
        # 네트워크 계열 예외(타임아웃·연결 끊김·JSON 아님)를 RuntimeError 로 바꾼다.
        # 그대로 두면 호출자의 except RuntimeError 에 안 걸려 프로세스가 죽고,
        # 이후 항목 발송과 상태 저장이 통째로 날아간다.
        try:
            resp = requests.post(url, json=payload, timeout=20)
            return {"_status": resp.status_code, **resp.json()}
        except requests.RequestException as exc:
            raise RuntimeError(f"텔레그램 요청 실패: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"텔레그램 응답 파싱 실패: {exc}") from exc

    data = post()
    if data.get("_status") == 429:
        # flood control. 텔레그램이 알려주는 대기 시간만큼 쉬고 한 번만 더 시도한다.
        wait = (data.get("parameters") or {}).get("retry_after", 5)
        print(f"[telegram] flood control: {wait}초 대기 후 재시도")
        time.sleep(min(int(wait) + 1, 60))
        data = post()

    if not data.get("ok"):
        raise RuntimeError(f"텔레그램 발송 실패: {data}")
    return data
