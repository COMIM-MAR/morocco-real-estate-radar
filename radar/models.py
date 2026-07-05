from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone


@dataclass
class Signal:
    channel: str
    source: str
    title: str
    url: str
    text: str
    city: str | None = None
    zone: str | None = None
    asset_type: str | None = None
    price_mad: int | None = None
    opportunity_score: int = 0
    confidence_score: int = 0
    total_score: int = 0
    status: str = "watch"
    reasons: list[str] = field(default_factory=list)
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)
