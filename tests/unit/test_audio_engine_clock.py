from fractions import Fraction

import pytest

from wsl2_audio.source_clock import SampleSpan, SourceClock, plan_windows


def test_exact_media_origin_and_resampling_do_not_accumulate_drift():
    clock = SourceClock(44100, 44100 * 3600, origin_num=-1, origin_den=1000)
    assert clock.media_time(44100 * 3600) == Fraction(3599999, 1000)
    assert clock.resample_span(SampleSpan(44099, 44101), 16000) == SampleSpan(15999, 16001)
    assert clock.resample_span(SampleSpan(0, 44100 * 3600), 16000).end == 57600000


@pytest.mark.parametrize("start,end", [(0, 0), (-1, 1), (2, 1), (True, 2), (0, 2.0)])
def test_invalid_sample_spans_are_rejected(start, end):
    with pytest.raises(ValueError):
        SampleSpan(start, end)


@pytest.mark.parametrize("rate,count,num,den", [
    (0, 10, 0, 1), (16000, 0, 0, 1), (True, 10, 0, 1),
    (16000, 10.0, 0, 1), (16000, 10, 0, 0), (16000, 10, 0, -1),
    (16000, 10, float("nan"), 1),
])
def test_invalid_clock_is_not_silently_coerced(rate, count, num, den):
    with pytest.raises(ValueError):
        SourceClock(rate, count, num, den)


def test_source_bounds_are_checked_before_mapping():
    clock = SourceClock(16000, 80001)
    with pytest.raises(ValueError):
        clock.media_time(80002)
    with pytest.raises(ValueError):
        clock.media_time(-1)
    with pytest.raises(ValueError):
        clock.resample_span(SampleSpan(80000, 80002), 48000)
    with pytest.raises(ValueError):
        clock.resample_span(SampleSpan(0, 10), True)


def test_window_cores_cover_short_tail_once_and_context_stays_in_source():
    clock = SourceClock(16000, 80001)
    windows = list(plan_windows(clock, core_samples=40000, context_samples=8000))
    assert [w.core for w in windows] == [SampleSpan(0, 40000), SampleSpan(40000, 80000), SampleSpan(80000, 80001)]
    assert [w.context for w in windows] == [SampleSpan(0, 48000), SampleSpan(32000, 80001), SampleSpan(72000, 80001)]
    assert [w.index for w in windows] == [0, 1, 2]
    assert sum(w.core.end - w.core.start for w in windows) == clock.sample_count


@pytest.mark.parametrize("core,context", [(0, 1), (10, -1), (True, 1), (10, 1.5)])
def test_invalid_window_configuration_fails_visibly(core, context):
    with pytest.raises(ValueError):
        list(plan_windows(SourceClock(16000, 16000), core, context))


def test_window_plan_is_lazy_for_long_recordings():
    clock = SourceClock(16000, 16000 * 60 * 60 * 24)
    windows = plan_windows(clock, 8000, 0)
    assert iter(windows) is windows
    assert next(windows).core == SampleSpan(0, 8000)
    assert next(windows).core == SampleSpan(8000, 16000)
