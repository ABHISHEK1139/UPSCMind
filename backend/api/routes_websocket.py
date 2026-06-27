"""
Hermes V2 — WebSocket Route
═══════════════════════════════════════════════════════════════
Real-time WebSocket endpoint for streaming agent state
to the React frontend (Agent Observatory).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# Active WebSocket connections
_active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(None, description="JWT token for authentication"),
) -> None:
    """
    WebSocket endpoint for real-time agent state streaming.

    The frontend connects to ws://host/api/ws/{session_id}?token=<JWT> to
    receive real-time updates as the LangGraph orchestrator
    processes a question.
    """
    # Authenticate via JWT token
    if token:
        try:
            from api.security import verify_token
            verify_token(token)
        except Exception:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    await websocket.accept()
    _active_connections[session_id] = websocket
    logger.info("[WS] Client connected: session=%s", session_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "event": "connection.established",
            "session_id": session_id,
            "message": "Connected to Hermes V2 real-time stream.",
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )
                message = json.loads(data)
                event = message.get("event", "")

                if event == "ping":
                    await websocket.send_json({"event": "pong"})
                elif event == "disconnect":
                    break
                else:
                    logger.debug("[WS] Received: %s", event)

            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"event": "keepalive"})

    except WebSocketDisconnect:
        logger.info("[WS] Client disconnected: session=%s", session_id)
    except Exception as exc:
        logger.error("[WS] Error: %s", exc)
    finally:
        _active_connections.pop(session_id, None)


async def broadcast_event(session_id: str, event: str, data: Dict[str, Any]) -> None:
    """
    Broadcast an event to a specific WebSocket client.

    Called by the event bus subscriber when agent state changes.
    """
    ws = _active_connections.get(session_id)
    if ws is None:
        return
    try:
        await ws.send_json({"event": event, "data": data, "session_id": session_id})
    except Exception as exc:
        logger.warning("[WS] Broadcast failed for %s: %s", session_id, exc)
        _active_connections.pop(session_id, None)


async def broadcast_to_all(event: str, data: Dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    disconnected = []
    for session_id, ws in _active_connections.items():
        try:
            await ws.send_json({"event": event, "data": data})
        except Exception:
            disconnected.append(session_id)
    for sid in disconnected:
        _active_connections.pop(sid, None)
