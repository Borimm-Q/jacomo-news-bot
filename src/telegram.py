"""텔레그램 채널 발행 모듈."""
import requests

import config

_API = "https://api.telegram.org/bot{token}/sendMessage"

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
                   source: str = "") -> str:
    """발행 메시지 본문(HTML)을 만듭니다."""
    label = _CATEGORY_LABEL.get(category, "속보")
    title_ko = _esc(title_ko.strip())
    summary_ko = _esc(summary_ko.strip())
    src_txt = f" · {_esc(source)}" if source else ""

    lines = [
        f"🚨 <b>[속보] {title_ko}</b>",
        "",
        summary_ko,
        "",
        f"🏷️ {label}{src_txt}",
    ]
    if url:
        lines.append(f'🔗 <a href="{_esc(url)}">원문 보기</a>')
    return "\n".join(lines)


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

    resp = requests.post(
        _API.format(token=config.TELEGRAM_BOT_TOKEN()),
        json=payload,
        timeout=20,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"텔레그램 발송 실패: {data}")
    return data
