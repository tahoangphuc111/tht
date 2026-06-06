import asyncio
import json
import logging
from typing import Any, Set

logger = logging.getLogger(__name__)

connected_websockets: Set[Any] = set()


async def _send_message(send_callable, text):
    try:
        await send_callable({"type": "websocket.send", "text": text})
    except Exception:
        logger.exception("Websocket send failed")
        # Safely remove the connection from list
        for item in list(connected_websockets):
            if isinstance(item, tuple) and item[0] == send_callable:
                connected_websockets.discard(item)
            elif item == send_callable:
                connected_websockets.discard(item)


def _broadcast_text(text_data):
    for item in list(connected_websockets):
        if isinstance(item, tuple):
            send_callable, loop = item
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(_send_message(send_callable, text_data), loop)
        else:
            # Fallback for direct ASGI calls
            send_callable = item
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(_send_message(send_callable, text_data))
            except RuntimeError:
                # Synchronous fallback
                new_loop = asyncio.new_event_loop()
                try:
                    new_loop.run_until_complete(_send_message(send_callable, text_data))
                finally:
                    new_loop.close()


def broadcast_vote_update(payload):
    message = {"type": "vote_update", "payload": payload}
    _broadcast_text(json.dumps(message))


def broadcast_badge_award(user_id, badge_name, badge_desc, badge_icon_url):
    message = {
        "type": "badge_award",
        "payload": {
            "user_id": user_id,
            "badge_name": badge_name,
            "badge_desc": badge_desc,
            "badge_icon_url": badge_icon_url,
        }
    }
    _broadcast_text(json.dumps(message))
