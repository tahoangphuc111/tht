"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os
import json

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_app = get_asgi_application()

connected_websockets = set()

from asgiref.sync import async_to_sync

def broadcast_vote_update(payload):
    from json import dumps
    message = {'type': 'vote_update', 'payload': payload}
    for conn in list(connected_websockets):
        try:
            async_to_sync(conn)({'type': 'websocket.send', 'text': dumps(message)})
        except Exception:
            connected_websockets.discard(conn)

async def websocket_app(scope, receive, send):
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
                        await conn({'type': 'websocket.send', 'text': json.dumps(broadcast)})
                    except Exception:
                        connected_websockets.discard(conn)
            elif event['type'] == 'websocket.disconnect':
                break
    finally:
        connected_websockets.discard(send)


async def application(scope, receive, send):
    if scope['type'] == 'websocket':
        if scope.get('path') == '/ws/votes/':
            await websocket_app(scope, receive, send)
        else:
            await send({'type': 'websocket.close', 'code': 1000})
    else:
        await django_app(scope, receive, send)

