"""Live updates to every open page (Server-Sent Events)."""
import asyncio

subscribers: set[asyncio.Queue] = set()


def broadcast(event: dict) -> None:
    for q in list(subscribers):
        q.put_nowait(event)
