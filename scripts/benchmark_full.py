"""Full-video acceptance benchmark; never extrapolate a short clip."""
import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.worker import claim, run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video',type=Path)
    parser.add_argument('--lighting',choices=['day','auto','night'],default='auto')
    parser.add_argument('--output',type=Path,default=Path('artifacts/benchmark-full.json'))
    args=parser.parse_args()
    with TestClient(app) as client:
        with args.video.open('rb') as source:
            response=client.post('/api/videos',files={'file':(args.video.name,source,'video/mp4')})
        response.raise_for_status();video=response.json()
        if video['duration']<900: raise ValueError('NF-01 requires at least 900 seconds of real video')
        response=client.post('/api/runs',json={'video_id':video['id'],'lighting':args.lighting,'sample_fps':6})
        response.raise_for_status();job=claim()
        if job is None or job['id']!=response.json()['id']: raise RuntimeError('Use an isolated empty INNOVA_DATA for this benchmark')
        print(f"Processing full {video['duration']:.2f}s clip, run={job['id']}",flush=True)
        begun=time.monotonic();run(job);elapsed=time.monotonic()-begun
        detail=client.get('/api/runs/'+job['id']).json()
        result=client.get('/api/runs/'+job['id']+'/results').json()
    cgroup=Path('/sys/fs/cgroup/cpu.max')
    metadata={'duration_s':video['duration'],'wall_s_including_model_load':elapsed,
              'passed_time_limit':detail['status']=='completed' and elapsed<=1800,
              'platform':platform.platform(),'python':platform.python_version(),
              'container':Path('/.dockerenv').exists(),
              'cpu_max':cgroup.read_text().strip() if cgroup.exists() else None,
              'performance':result['performance'],'events':result['summary']['total'],
              'clusters':len(result['clusters']['clusters']),
              'video_sha256':hashlib.sha256(args.video.read_bytes()).hexdigest(),
              'note':'Performance only; no accuracy claim without independent annotation.'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2),flush=True)
    if not metadata['passed_time_limit']: raise SystemExit(1)


if __name__=='__main__':main()
