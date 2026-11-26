"""Create synthetic UI fixtures only in an explicitly configured test data root."""
import io
import json
import os
import sys
from pathlib import Path
if not os.environ.get('INNOVA_DATA'):
    raise SystemExit('Set INNOVA_DATA to an isolated test directory')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import av
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.storage import connection

video=io.BytesIO()
with av.open(video,mode='w',format='mp4') as output:
    stream=output.add_stream('libx264',rate=5);stream.width=320;stream.height=180;stream.pix_fmt='yuv420p'
    for i in range(25):
        frame=av.VideoFrame.from_image(Image.new('RGB',(320,180),(20+i*2,35,40)))
        for packet in stream.encode(frame):output.mux(packet)
    for packet in stream.encode():output.mux(packet)
with TestClient(app) as client:
    item=client.post('/api/videos',files={'file':('UI fixture.mp4',video.getvalue(),'video/mp4')}).json()
    run=client.post('/api/runs',json={'video_id':item['id']}).json()
    client.post('/api/runs/'+run['id']+'/events',json={'category':'car','time_s':1,'from_direction':'В кадре','to_direction':'В кадре'})
    with connection() as db:
        db.execute("UPDATE runs SET status='completed',progress=1,message='Synthetic UI fixture' WHERE id=?",(run['id'],))
print(json.dumps({'video':item['id'],'run':run['id']}))
