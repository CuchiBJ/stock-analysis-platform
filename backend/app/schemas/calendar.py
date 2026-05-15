from pydantic import BaseModel
from datetime import date
from typing import List


class EventBase(BaseModel):
    date: date
    type: str
    title: str
    importance: str
    description: str | None = None


class Event(EventBase):
    id: str
    affected_symbols: List[str]

    class Config:
        from_attributes = True
