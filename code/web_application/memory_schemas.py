from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ChatIn(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    session_id: Optional[str] = Field(default=None, max_length=100)
    message: str = Field(min_length=1, max_length=4000)


class ShortTermMessage(BaseModel):
    role: str
    content: str


class EpisodeFact(BaseModel):
    fact: str
    importance: float


class MemoryUsed(BaseModel):
    short_term_count: int
    short_term: List[ShortTermMessage]
    long_term_summary: Optional[str] = None
    episodic_facts: List[EpisodeFact]


class ChatOut(BaseModel):
    session_id: str
    reply: str
    used: MemoryUsed


class StoredMessage(BaseModel):
    user_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class StoredSummary(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    scope: str
    text: str
    created_at: datetime


class StoredEpisode(BaseModel):
    user_id: str
    session_id: str
    fact: str
    importance: float
    created_at: datetime


class MemoryOut(BaseModel):
    messages: List[StoredMessage]
    session_summary: Optional[StoredSummary] = None
    lifetime_summary: Optional[StoredSummary] = None
    episodes: List[StoredEpisode]


class DailyCount(BaseModel):
    date: str
    count: int


class AggregateOut(BaseModel):
    daily_counts: List[DailyCount]
    recent_summaries: List[StoredSummary]
