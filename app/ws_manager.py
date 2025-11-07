from typing import Dict, Set
from fastapi import WebSocket
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        # room_id -> set of websockets
        self.active: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, room: str, websocket: WebSocket):
        await websocket.accept()
        self.active[room].add(websocket)

    def disconnect(self, room: str, websocket: WebSocket):
        if websocket in self.active.get(room, set()):
            self.active[room].remove(websocket)

    async def broadcast(self, room: str, message: dict):
        conns = list(self.active.get(room, []))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                # best-effort
                pass
