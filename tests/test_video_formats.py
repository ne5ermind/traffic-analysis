import subprocess
import pytest
from backend.video import inspect_video
from backend.main import VIDEO_EXTENSIONS


@pytest.mark.parametrize('extension,codec,size', [
    ('mp4','libx264','640x360'), ('mov','libx264','360x640'), ('m4v','libx264','320x240'),
    ('mkv','libx264','1280x720'), ('avi','mpeg4','160x120'), ('webm','libvpx-vp9','320x180'),
    ('mts','libx264','320x240'), ('m2ts','libx264','320x240'),
])
def test_actual_containers_and_resolutions(tmp_path, extension, codec, size):
    path = tmp_path / f'video.{extension}'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size={size}:rate=10', '-t','1','-c:v',codec,str(path)], check=True)
    value = inspect_video(path, tmp_path / 'preview.jpg')
    assert '.' + extension in VIDEO_EXTENSIONS
    assert (value['width'], value['height']) == tuple(map(int, size.split('x')))
    assert value['frame_count'] >= 9
    assert value['duration'] > 0
