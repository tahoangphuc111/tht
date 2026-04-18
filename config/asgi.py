"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
import json
from asgiref.sync import async_to_sync
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_app = get_asgi_application()

connected_websockets = set()


def broadcast_vote_update(payload):
    """Broadcast vote updates to all connected websocket clients."""
    message = {'type': 'vote_update', 'payload': payload}
    for conn in list(connected_websockets):
        try:
            async_to_sync(conn)({
                'type': 'websocket.send',
                'text': json.dumps(message)
            })
        except Exception:  # pylint: disable=broad-exception-caught
            connected_websockets.discard(conn)


async def websocket_app(scope, receive, send):
    """Handle websocket connections and messages."""
    assert scope['type'] == 'websocket'
    await send({'type': 'websocket.accept'})
    connected_websockets.add(send)
    try:
        while True:
            event = await receive()
            if event['type'] == 'websocket.receive':
                text = event.get('text')
                if text is None:
                    continue
                data = json.loads(text)
                # Broadcast vote updates to all connected clients.
                broadcast = {
                    'type': 'vote_update',
                    'payload': data,
                }
                for conn in list(connected_websockets):
                    try:
                        await conn({
                            'type': 'websocket.send',
                            'text': json.dumps(broadcast)
                        })
                    except Exception:  # pylint: disable=broad-exception-caught
                        connected_websockets.discard(conn)
            elif event['type'] == 'websocket.disconnect':
                break
    finally:
        connected_websockets.discard(send)


async def application(scope, receive, send):
    """Main entry point for ASGI application."""
    if scope['type'] == 'websocket':
        if scope.get('path') == '/ws/votes/':
            await websocket_app(scope, receive, send)
        else:
            await send({'type': 'websocket.close', 'code': 1000})
    else:
        await django_app(scope, receive, send)
