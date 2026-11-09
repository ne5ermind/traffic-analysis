import pytest

from app.sampling import FrameSampler, budgeted_fps


def test_sample_by_timestamps_including_variable_frame_rate():
    sampler = FrameSampler(2)
    times = [0.0, 0.1, 0.2, 0.4, 0.55, 0.8, 1.1, 1.2, 1.52]
    assert [t for t in times if sampler.accept(t)] == [0.0, 0.55, 1.1, 1.52]


def test_sample_after_discontinuity_without_catching_up():
    sampler = FrameSampler(6)
    assert sampler.accept(0)
    assert sampler.accept(120)
    assert not sampler.accept(120.01)


def test_sample_recovers_when_container_timestamps_restart():
    sampler = FrameSampler(2)
    assert sampler.accept(10)
    assert not sampler.accept(10.1)
    assert sampler.accept(0)  # New timestamp epoch.
    assert not sampler.accept(0.1)
    assert sampler.accept(0.5)


def test_adaptive_rate_keeps_fast_machines_fast_and_slows_docker_like_cpu():
    assert budgeted_fps(6, video_seconds=30, wall_seconds=7) == 6
    assert budgeted_fps(6, video_seconds=30, wall_seconds=47) == 5.5
    assert budgeted_fps(6, video_seconds=30, wall_seconds=110) == 2
    assert budgeted_fps(6, video_seconds=30, wall_seconds=300) == 2
    sampler = FrameSampler(6)
    assert sampler.accept(0)
    assert not sampler.accept(.1)
    sampler.set_rate(2)
    assert not sampler.accept(.3)
    assert sampler.accept(.5)


def test_sampling_rejects_non_finite_timing_inputs():
    sampler = FrameSampler(6)
    with pytest.raises(ValueError, match="конечным"):
        sampler.accept(float("nan"))
    with pytest.raises(ValueError, match="конечными"):
        budgeted_fps(6, float("inf"), 2)
    with pytest.raises(ValueError, match="положительной"):
        budgeted_fps(0, 30, 2)
