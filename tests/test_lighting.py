import numpy as np
from app.vision.lighting import LowLightProcessor


def test_night_enhances_luminance_without_changing_shape_or_day_frames():
    frame=np.full((64,96,3),25,dtype=np.uint8)
    enhanced,dark=LowLightProcessor('night').process(frame)
    assert dark and enhanced.mean()>frame.mean()
    assert enhanced.shape==frame.shape and enhanced.dtype==frame.dtype
    day, dark=LowLightProcessor('day').process(frame)
    assert day is frame and not dark


def test_auto_uses_hysteresis_and_recovers_in_daylight():
    processor=LowLightProcessor('auto')
    dark=np.full((32,32,3),10,dtype=np.uint8)
    bright=np.full((32,32,3),220,dtype=np.uint8)
    assert processor.process(dark)[1]
    assert processor.process(bright)[1]  # a single headlight does not reset the model
    for _ in range(20): output,is_dark=processor.process(bright)
    assert not is_dark and output is bright
