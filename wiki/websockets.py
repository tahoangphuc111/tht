import asyncio
import json
from typing import Any, Set
from asgiref.sync import async_to_sync

connected_websockets: Set[Any] = set()


async def _send_message(send_callable, text):
    """Internal helper to send a message and handle cleanup."""
    try:
        await send_callable({"type": "websocket.send", "text": text})
    except Exception:
        connected_websockets.discard(send_callable)


def broadcast_vote_update(payload):
    """
    Broadcast vote updates to all connected websocket clients.
    Uses an event loop if available to avoid blocking the caller.
    """
    message = {"type": "vote_update", "payload": payload}
    text_data = json.dumps(message)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            for send_callable in list(connected_websockets):
                loop.create_task(_send_message(send_callable, text_data))
            return
    except RuntimeError:
        pass

    for send_callable in list(connected_websockets):
        try:
            async_to_sync(send_callable)(
                {"type": "websocket.send", "text": text_data}
            )
        except Exception:
            connected_websockets.discard(send_callable)
