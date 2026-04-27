import asyncio
import json
from typing import Any, Set
from asgiref.sync import async_to_sync

connected_websockets: Set[Any] = set()


async def _send_message(send_callable, text):
    try:
        await send_callable({"type": "websocket.send", "text": text})
    except Exception:
        connected_websockets.discard(send_callable)


def broadcast_vote_update(payload):
    message = {"type": "vote_update", "payload": payload}
    text_data = json.dumps(message)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        for send_callable in list(connected_websockets):
            loop.create_task(_send_message(send_callable, text_data))
    else:
        async def _run_all():
            tasks = [_send_message(s, text_data) for s in list(connected_websockets)]
            if tasks:
                await asyncio.gather(*tasks)
        loop.run_until_complete(_run_all())
