from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class Opportunity:
    source: str
    title: str
    url: str
    text: str
    city: str | None = None
    zone: str | None = None
    asset_type: str | None = None
    price_mad: int | None = None
    score: int = 0
    urgency: str = "watch"
    reasons: list[str] | None = None
    detected_at: str = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
