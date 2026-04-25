"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import asyncio
import json
import os
from typing import Any, Set

from asgiref.sync import async_to_sync
from django.core.asgi import get_asgi_application
from wiki.websockets import connected_websockets

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_app = get_asgi_application()


async def websocket_app(scope, receive, send):
    """Handle websocket connections and messages."""
    assert scope["type"] == "websocket"

    # Basic authentication check if user is in scope (provided by some ASGI servers/middleware)
    user = scope.get("user")
    if user and not user.is_authenticated:
        await send({"type": "websocket.close", "code": 4001})
        return

    await send({"type": "websocket.accept"})
    connected_websockets.add(send)
    try:
        while True:
            event = await receive()
            if event["type"] == "websocket.receive":
                try:
                    data = json.loads(event.get("text", "{}"))
                    if data.get("type") == "ping":
                        await send({"type": "websocket.send", "text": json.dumps({"type": "pong"})})
                except json.JSONDecodeError:
                    pass
            elif event["type"] == "websocket.disconnect":
                break
    finally:
        connected_websockets.discard(send)


async def application(scope, receive, send):
    """Main entry point for ASGI application."""
    if scope["type"] == "websocket":
        if scope.get("path") == "/ws/votes/":
            await websocket_app(scope, receive, send)
        else:
            await send({"type": "websocket.close", "code": 1000})
    else:
        await django_app(scope, receive, send)
