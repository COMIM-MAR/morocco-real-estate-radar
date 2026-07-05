from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SignalEvent:
    collector: str
    channel: str
    source: str
    signal_type: str
    title: str
    url: str
    text: str
    is_primary: bool
    launch_weight: int = 0
    confidence_weight: int = 0
    metadata: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    discovered_at: str = field(default_factory=now_iso)
    city_hint: str | None = None
    zone_hint: str | None = None
    promoter_hint: str | None = None
    asset_type_hint: str | None = None
    project_name_hint: str | None = None
    price_mad: int | None = None
    signal_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.signal_id = hashlib.sha1(f"{self.collector}|{self.channel}|{self.url}".encode()).hexdigest()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProjectRecord:
    project_id: str
    name: str
    city: str | None
    zone: str | None
    promoter: str | None
    asset_type: str | None
    first_detected_at: str
    last_updated_at: str
    launch_score: int
    confidence_score: int
    investment_score: int
    urgency_score: int
    recommendation: str
    status: str
    summary: str
    prices: dict
    aliases: list[str]
    channels: list[str]
    sources: list[str]
    source_urls: list[str]
    evidence: dict
    reasons: list[str]
    timeline: list[dict] = field(default_factory=list)
    signals: list[SignalEvent] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["signals"] = [signal.to_dict() for signal in self.signals]
        return payload
