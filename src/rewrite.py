"""Claude(Haiku)로 수집 항목을 가공합니다.

역할:
1) 발행 여부 판단(필터) — 가격 급등락 단순 알림, 자두두 관련, 광고/사기성, 무의미 항목 제외
2) 사실만 추출해 한국어 친절체로 재작성 (원문 문장 복제 금지 = 저작권 안전)
3) 카테고리 분류

원문 표현을 그대로 옮기지 않고 '사실'만 새 문장으로 쓰므로 한국 저작권법상
'사실의 전달에 불과한 시사보도'(제7조 5호) 범위에서 안전하게 운영됩니다.
"""
import json

import anthropic

import config

_RULES = """\
너는 한국 투자자 커뮤니티 텔레그램 '속보' 채널의 편집자야.
코인뿐 아니라 시장 전반(거래소 공지, 코인, 매크로 경제, 금리/환율/유가,
지정학, 주요 기업/규제 소식)을 받아서, 한국인이 보기 좋게 가공한다.

[매우 중요한 규칙]
1. 원문 문장을 절대 그대로 옮기지 마라. 사실(누가/무엇을/언제/수치)만 뽑아 네 문장으로 새로 써라.
2. 한국어로만 쓴다. 문체는 신문 속보처럼 '~다/~이다' 평서문 종결로, 간결하고 사무적으로 써라.
   예) '합의했다', '발표했다', '중단한다', '인상했다', 'A는 B이다'. 딱딱하고 봇 같은 톤도 괜찮다.
3. 'news'(사실 보도) 항목에는 우리 해석을 덧붙이지 마라. 일어난 사실만 평서문(~다)으로 전한다.
   ('~로 보인다', '~할 전망이다', '시장에 호재/악재' 같은 해석성 서술을 사실 뉴스에 붙이지 말 것)
   단, 원문 자체가 분석·전망·논평·해설 기사이면 그 내용을 요약하되 kind="analysis"로 분류한다.
4. 아래에 해당하면 발행하지 않는다(publish=false):
   - 단순 가격 급등락/시세 변동 알림 (예: "비트코인 5% 상승", "ETF 26억 이동" 같은 시세·자금이동 그 자체)
   - '자두두' 유튜버나 '자코모' 커뮤니티와 관련된 내용
   - 광고, 홍보, 에어드랍 유도, 사기 의심, 도박성, 유료 구독 권유
   - 제목만으로 무슨 일인지 알 수 없거나 가치가 낮은 잡담성 내용
5. 단, 매크로/지정학/경제지표/규제/기업 소식은 '사실'이면 발행한다(코인과 무관해도 OK).
6. 발행할 때 summary_ko 는 2~3문장으로 핵심 사실만 담는다.
7. category 는 내용에 맞게 고른다:
   - "exchange": 거래소 공식 공지(상장/이벤트/점검 등)
   - "crypto": 코인·블록체인 관련 소식
   - "market": 매크로 경제·금리/환율/유가·지정학·기업/규제 소식
8. 중요도가 낮으면 발행하지 않는다(publish=false): 정기 시세브리핑/마감시황, 사소한 업데이트,
   별 의미 없는 일정 안내, 단신 나열 등. "이게 속보로 알릴 만한가?" 아니면 거른다.
9. 한국어 기사(토큰포스트·블록미디어 등)도 원문 표현을 그대로 옮기지 마라. 사실만 뽑아
   완전히 새 문장으로 바꿔 써라. (한국어→한국어라도 베끼기 금지)
10. kind 를 정한다: 일어난 사실을 전하는 보도면 "news", 원문이 분석·전망·논평·해설 위주면 "analysis"."""

# 단건 처리용
_SYSTEM = _RULES + """

[출력 형식]
아무 설명 없이 아래 JSON 하나만 출력해라:
{
  "publish": true 또는 false,
  "reason": "발행하지 않는다면 그 이유(한국어, 한 줄)",
  "title_ko": "한 줄 한국어 제목(평서문 ~다)",
  "summary_ko": "2~3문장 한국어 요약(평서문 ~다)",
  "category": "exchange" 또는 "crypto" 또는 "market",
  "kind": "news" 또는 "analysis"
}"""

# 여러 건을 한 번에 처리(배칭)용 — 비용 절감 핵심
_SYSTEM_BATCH = _RULES + """

[중복 제거 — 매우 중요, 반드시 지켜라]
A. 같은 배치 안에서 '같은 사건'을 다루는 항목이 여러 개면(여러 매체가 같은 뉴스를 보도),
   그중 가장 정보가 풍부한 딱 1개만 publish=true 로 하고, 나머지는 전부 publish=false,
   reason="중복" 으로 처리해라.
B. 입력 끝에 [최근 이미 발행한 속보] 목록이 주어지면, 새 항목이 그 목록의 어느 것과
   '같은 사건'이면 publish=false, reason="이미 발행" 으로 처리해라.
같은 사건 판단은 제목이 글자 그대로 같지 않아도, 핵심 사실(주체·사건)이 동일하면 같은 것으로 본다.

[출력 형식]
여러 건을 한 번에 받는다. 각 항목 앞의 번호([0], [1] ...)를 그대로 써서,
아무 설명 없이 아래 형태의 JSON 배열 하나만 출력해라:
[
  {"index": 0, "publish": true/false, "reason": "...", "title_ko": "...", "summary_ko": "...", "category": "exchange|crypto|market", "kind": "news|analysis"},
  {"index": 1, ...}
]
입력으로 받은 모든 번호에 대해 정확히 하나씩 객체를 만들어야 한다."""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY())
    return _client


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # ```json 형태 제거
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def process(item: dict) -> dict | None:
    """한 항목을 가공한다.

    반환: 발행할 항목이면 가공된 dict, 발행하지 않으면 None.
    (성공/실패와 무관하게 호출자는 이 항목을 'seen'으로 기록해 재시도를 막는다.)
    """
    user_msg = (
        f"출처 유형: {item['source_type']}\n"
        f"출처명: {item['source_name']}\n"
        f"제목: {item['title']}\n"
        f"본문/추가정보: {item.get('body') or '(없음)'}\n"
        f"링크: {item['url']}"
    )

    try:
        resp = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text")
    except Exception as exc:  # noqa: BLE001 - 어떤 API 오류든 이 항목만 건너뜀
        print(f"[rewrite] Claude 호출 실패(건너뜀): {exc}")
        return None

    data = _parse_json(raw)
    if not data:
        print(f"[rewrite] JSON 파싱 실패(건너뜀): {raw[:120]!r}")
        return None

    return _to_result(data, item)


def _to_result(data: dict, item: dict) -> dict | None:
    """Claude 판정(dict)을 발행용 결과로 변환. 발행 안 하면 None."""
    if not data.get("publish"):
        print(f"[rewrite] 제외: {item['title'][:40]} → {data.get('reason', '')}")
        return None
    return {
        "title_ko": data.get("title_ko") or item["title"],
        "summary_ko": data.get("summary_ko") or "",
        "category": data.get("category") or item["source_type"],
        "kind": "analysis" if data.get("kind") == "analysis" else "news",
        "url": item["url"],
        "source_name": item["source_name"],
        "published_at": item.get("published_at"),  # 신선도 태그 계산용
    }


def _parse_json_array(text: str) -> list | None:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


def process_batch(items: list[dict], recent_titles: list[str] | None = None) -> list[dict]:
    """여러 항목을 한 번의 Claude 호출로 가공(배칭) — 비용 절감용.

    recent_titles: 최근 이미 발행한 속보 제목들. 새 항목이 이와 같은 사건이면 거른다(회차 간 중복 방지).
    반환: 발행할 결과 dict들의 리스트(입력 순서 유지). 발행 제외분은 빠진다.
    호출자는 입력 items 전부를 'seen'으로 기록해야 한다(발행 여부 무관).
    """
    if not items:
        return []

    numbered = []
    for i, it in enumerate(items):
        body = (it.get("body") or "(없음)")[:300]
        numbered.append(
            f"[{i}] 출처유형:{it['source_type']} | 출처:{it['source_name']} | "
            f"제목:{it['title']} | 본문:{body} | 링크:{it['url']}"
        )
    user_msg = "다음 여러 건을 각각 판정해라:\n\n" + "\n\n".join(numbered)

    if recent_titles:
        recent_block = "\n".join(f"- {t}" for t in recent_titles[:60])
        user_msg += f"\n\n[최근 이미 발행한 속보]\n{recent_block}"

    try:
        resp = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=min(400 * len(items) + 200, 8000),
            system=_SYSTEM_BATCH,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(b.text for b in resp.content if b.type == "text")
    except Exception as exc:  # noqa: BLE001
        print(f"[rewrite] Claude 배치 호출 실패(전체 건너뜀): {exc}")
        return []

    arr = _parse_json_array(raw)
    if arr is None:
        print(f"[rewrite] 배치 JSON 파싱 실패(전체 건너뜀): {raw[:150]!r}")
        return []

    by_index = {d.get("index"): d for d in arr if isinstance(d, dict)}
    results = []
    for i, it in enumerate(items):
        data = by_index.get(i)
        if not data:
            print(f"[rewrite] 배치 응답 누락(건너뜀): [{i}] {it['title'][:40]}")
            continue
        result = _to_result(data, it)
        if result:
            results.append(result)
    return results
