import logging

import httpx

logger = logging.getLogger("morning_brief.telegram")


async def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
) -> tuple[bool, str]:
    """
    Send an HTML formatted message via Telegram Bot API using httpx POST.
    Returns (success, response_message).
    """
    if not bot_token or not chat_id:
        msg = "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing. Message delivery skipped."
        logger.error(msg)
        return False, msg

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            resp_data = resp.json()

        if resp.status_code == 200 and resp_data.get("ok"):
            logger.info("Successfully sent morning briefing to Telegram.")
            return True, "Delivered"
        else:
            description = resp_data.get("description", "Unknown Telegram API error")
            logger.error(f"Telegram API error ({resp.status_code}): {description}")
            return False, f"Telegram API Error: {description}"

    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False, str(e)
