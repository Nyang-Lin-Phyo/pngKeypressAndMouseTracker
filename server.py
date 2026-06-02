"""
PNGvtuber WebSocket server
Reads global keyboard + mouse input and broadcasts state to the browser overlay.

Install deps:
    pip install websockets keyboard mouse

Run:
    python server.py
"""

import asyncio
import json
import threading
import websockets
import keyboard
import mouse

# ── Config ───────────────────────────────────────────────────────────────────
HOST = "localhost"
PORT = 8765

TRACKED_KEYS = {'1','2','3','4','q','w','e','r','a','s','d','f','space'}

# ── Shared state ──────────────────────────────────────────────────────────────
_press_order: list = []
_mouse_x: int = 0
_mouse_y: int = 0
_state_lock = threading.Lock()
_clients: set = set()
_loop: asyncio.AbstractEventLoop = None

# ── Broadcast ─────────────────────────────────────────────────────────────────
async def _broadcast(message: str):
    if not _clients:
        return
    disconnected = set()
    for ws in list(_clients):
        try:
            await ws.send(message)
        except websockets.ConnectionClosed:
            disconnected.add(ws)
    _clients.difference_update(disconnected)


def _send_state():
    """Called from input threads — schedules a broadcast on the async loop."""
    if _loop is None:
        return
    with _state_lock:
        msg = json.dumps({
            "held_keys": list(_press_order),
            "mouse_x":   _mouse_x,
            "mouse_y":   _mouse_y,
        })
    asyncio.run_coroutine_threadsafe(_broadcast(msg), _loop)


# ── Keyboard hooks ────────────────────────────────────────────────────────────
def _on_key(event):
    key = event.name.lower()
    if key not in TRACKED_KEYS:
        return
    with _state_lock:
        if event.event_type == keyboard.KEY_DOWN:
            if key not in _press_order:
                _press_order.append(key)
        elif event.event_type == keyboard.KEY_UP:
            if key in _press_order:
                _press_order.remove(key)
    _send_state()


# ── Mouse hooks ───────────────────────────────────────────────────────────────
_last_mx = 0
_last_my = 0
MOUSE_THRESHOLD = 2

def _on_mouse(event):
    global _last_mx, _last_my, _mouse_x, _mouse_y
    if not isinstance(event, mouse.MoveEvent):
        return
    if abs(event.x - _last_mx) < MOUSE_THRESHOLD and \
       abs(event.y - _last_my) < MOUSE_THRESHOLD:
        return
    _last_mx = event.x
    _last_my = event.y
    with _state_lock:
        _mouse_x = event.x
        _mouse_y = event.y
    _send_state()


# ── WebSocket handler ─────────────────────────────────────────────────────────
async def _handler(websocket):
    _clients.add(websocket)
    print(f"[+] Client connected  ({len(_clients)} total)")
    try:
        # Send current state immediately
        with _state_lock:
            msg = json.dumps({
                "held_keys": list(_press_order),
                "mouse_x":   _mouse_x,
                "mouse_y":   _mouse_y,
            })
        await websocket.send(msg)
        await websocket.wait_closed()
    finally:
        _clients.discard(websocket)
        print(f"[-] Client disconnected ({len(_clients)} total)")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    global _loop
    _loop = asyncio.get_running_loop()

    keyboard.hook(_on_key)
    mouse.hook(_on_mouse)

    print(f"[*] PNGvtuber server running on ws://{HOST}:{PORT}")
    print(f"[*] Tracking keys: {', '.join(sorted(TRACKED_KEYS))}")
    print(f"[*] Press Ctrl+C to stop\n")

    async with websockets.serve(_handler, HOST, PORT):
        await asyncio.Future()  # run forever cleanly


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")