"""Versioned, renderer-neutral presentation commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PresentationCommand:
    profile: str
    behavior: str
    intensity: float = 1.0
    transition: str = "smooth"
    version: int = 1

    def __post_init__(self) -> None:
        if not self.profile or not self.behavior:
            raise ValueError("presentation profile and behavior must not be empty")
        if not 0.0 <= self.intensity <= 1.0:
            raise ValueError("presentation intensity must be between 0 and 1")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
