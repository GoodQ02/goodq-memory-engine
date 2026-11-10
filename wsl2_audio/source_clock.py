"""Exact recording time and bounded analysis windows; no model or scene policy."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterator


def _integer(value: int, name: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class SampleSpan:
    start: int
    end: int

    def __post_init__(self) -> None:
        _integer(self.start, "start", 0)
        _integer(self.end, "end", 1)
        if self.end <= self.start:
            raise ValueError("Sample span must have positive duration")

    def overlaps(self, other: "SampleSpan") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class SourceClock:
    sample_rate: int
    sample_count: int
    origin_num: int = 0
    origin_den: int = 1

    def __post_init__(self) -> None:
        _integer(self.sample_rate, "sample_rate", 1)
        _integer(self.sample_count, "sample_count", 1)
        _integer(self.origin_num, "origin_num")
        _integer(self.origin_den, "origin_den", 1)

    def require_span(self, span: SampleSpan) -> None:
        if not isinstance(span, SampleSpan) or span.end > self.sample_count:
            raise ValueError("Span is outside the source clock")

    def media_time(self, sample: int) -> Fraction:
        _integer(sample, "sample", 0)
        if sample > self.sample_count:
            raise ValueError("Sample is outside the source clock")
        return Fraction(self.origin_num, self.origin_den) + Fraction(sample, self.sample_rate)

    def resample_span(self, span: SampleSpan, target_rate: int) -> SampleSpan:
        self.require_span(span)
        _integer(target_rate, "target_rate", 1)
        start = span.start * target_rate // self.sample_rate
        end = (span.end * target_rate + self.sample_rate - 1) // self.sample_rate
        return SampleSpan(start, end)


@dataclass(frozen=True)
class AudioWindow:
    index: int
    core: SampleSpan
    context: SampleSpan


def plan_windows(clock: SourceClock, core_samples: int, context_samples: int) -> Iterator[AudioWindow]:
    """Partition the source into owned cores with independently bounded context."""
    _integer(core_samples, "core_samples", 1)
    _integer(context_samples, "context_samples", 0)
    for index, start in enumerate(range(0, clock.sample_count, core_samples)):
        end = min(start + core_samples, clock.sample_count)
        yield AudioWindow(index, SampleSpan(start, end), SampleSpan(
            max(0, start - context_samples), min(clock.sample_count, end + context_samples)
        ))
