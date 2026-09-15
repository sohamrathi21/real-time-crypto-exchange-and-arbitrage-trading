import json
from pydantic import BaseModel, Field
from .models import OrderBook, now_ms


class ReplayControl(BaseModel):
    action: str
    speed: float = Field(1, ge=1, le=10)


class ReplaySession:
    def __init__(self):
        self.frames = []
        self.index = 0
        self.playing = False
        self.speed = 1
        self.enabled = False
        self.next_due = 0
        self.session = 0

    def load(self, frames):
        last = -1
        for frame in frames:
            if not frame:
                raise ValueError("Replay frames must not be empty")
            stamp = max(b.received_at for b in frame)
            if stamp <= last:
                raise ValueError("Replay frames must be strictly chronological")
            last = stamp
        self.frames = frames
        self.index = 0
        self.playing = False
        self.enabled = True
        self.session += 1

    def tick(self):
        if not self.enabled or not self.playing or now_ms() < self.next_due:
            return []
        if self.index >= len(self.frames):
            self.playing = False
            return []
        frame = self.frames[self.index]
        stamp = max(b.received_at for b in frame)
        at = now_ms()
        books = []
        for b in frame:
            payload = b.model_dump()
            payload.update(
                source="replay",
                timestamp=at - (stamp - b.timestamp),
                received_at=at,
                sequence=f"replay:{self.session}:{self.index}:{b.sequence}",
            )
            books.append(OrderBook(**payload))
        self.index += 1
        delay = (
            (max(b.received_at for b in self.frames[self.index]) - stamp) / self.speed
            if self.index < len(self.frames)
            else 1000
        )
        self.next_due = at + max(50, delay)
        return books

    def snapshot(self):
        return dict(
            enabled=self.enabled,
            playing=self.playing,
            speed=self.speed,
            index=self.index,
            total=len(self.frames),
        )
