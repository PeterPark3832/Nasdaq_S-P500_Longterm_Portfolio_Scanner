"""
텔레그램 메시지 발송 / 수신 — 순수 I/O 레이어
"""
import logging
import time

import requests

from scanner.config import TELEGRAM_TOKEN, TELEGRAM_CHAT_IDS, TELEGRAM_TOPIC_ID

log = logging.getLogger("scanner")


def _is_supergroup(chat_id: str) -> bool:
    return str(chat_id).startswith("-100")


def _split_into_chunks(text: str, limit: int = 3800) -> list[str]:
    """긴 텍스트를 줄 단위로 잘라 limit 이하 청크 리스트로 반환."""
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current.strip():
                chunks.append(current.strip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        chunks.append(current.strip())
    return chunks


def send_telegram(text: str, topic_id: int | None = None) -> None:
    """모든 TELEGRAM_CHAT_IDS에 브로드캐스트."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_IDS:
        log.warning("텔레그램 설정 없음")
        return
    effective_topic = topic_id if topic_id is not None else TELEGRAM_TOPIC_ID
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
            if effective_topic is not None and _is_supergroup(chat_id):
                payload["message_thread_id"] = effective_topic
            res = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                data=payload, timeout=10,
            )
            if res.status_code != 200:
                log.error(f"텔레그램 실패 ({chat_id}): {res.text}")
        except Exception as e:
            log.error(f"텔레그램 예외 ({chat_id}): {e}")
        time.sleep(0.1)


def send_telegram_chunks(text: str, topic_id: int | None = None) -> None:
    """4000자 초과 메시지를 분할 발송."""
    if len(text) <= 4000:
        send_telegram(text, topic_id=topic_id)
        return
    for i, chunk in enumerate(_split_into_chunks(text)):
        if i > 0:
            time.sleep(0.5)
        send_telegram(chunk, topic_id=topic_id)


def reply_to(chat_id: str, text: str) -> None:
    """특정 채팅방에만 응답 (명령어 응답 전용)."""
    if not TELEGRAM_TOKEN:
        return
    try:
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        if TELEGRAM_TOPIC_ID is not None and _is_supergroup(chat_id):
            payload["message_thread_id"] = TELEGRAM_TOPIC_ID
        res = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=payload, timeout=10,
        )
        if res.status_code != 200:
            log.error(f"reply_to 실패 ({chat_id}): {res.text}")
    except Exception as e:
        log.error(f"reply_to 예외 ({chat_id}): {e}")


def reply_to_chunks(chat_id: str, text: str) -> None:
    if len(text) <= 4000:
        reply_to(chat_id, text)
        return
    for i, chunk in enumerate(_split_into_chunks(text)):
        if i > 0:
            time.sleep(0.5)
        reply_to(chat_id, chunk)


def get_updates(offset: int, timeout: int = 30) -> list[dict]:
    """텔레그램 Long-polling 업데이트 조회."""
    if not TELEGRAM_TOKEN:
        return []
    try:
        res = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"offset": offset, "timeout": timeout},
            timeout=timeout + 5,
        )
        if res.status_code == 200:
            return res.json().get("result", [])
    except Exception as e:
        log.warning(f"getUpdates 실패: {e}")
    return []
