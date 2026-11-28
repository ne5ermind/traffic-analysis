import React, {useEffect, useRef, useState} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {api, categories, timeLabel} from '../api';
import {addPoint, selectEditing, selectPending, selectVisibleGeometry} from '../store/sceneEditorSlice.js';
import {selectRunId, selectVideo} from '../store/workspaceSlice.js';

export function VideoPanel() {
  const dispatch = useDispatch();
  const video = useSelector(selectVideo);
  const runId = useSelector(state => selectEditing(state) ? '' : selectRunId(state));
  const geometry = useSelector(selectVisibleGeometry);
  const pending = useSelector(selectPending);
  const editing = useSelector(selectEditing);
  const player = useRef(null), canvas = useRef(null), sequence = useRef(0);
  const [time, setTime] = useState(0), [objects, setObjects] = useState([]), [mediaError, setMediaError] = useState('');
  useEffect(() => { setTime(0); setObjects([]); setMediaError(''); sequence.current++; }, [video?.id, runId]);
  useEffect(() => {
    setObjects([]);
    if (!runId) return;
    const controller = new AbortController(), request = ++sequence.current;
    api(`/api/runs/${runId}/results?view=detections&time_s=${time}`, {signal:controller.signal})
      .then(data => { if (request === sequence.current) setObjects(data.objects || []); })
      .catch(error => { if (error.name !== 'AbortError') setMediaError(error.message); });
    return () => controller.abort();
  }, [runId, time]);
  useEffect(() => {
    const target = canvas.current; if (!target) return;
    const draw = () => {
      const width = target.clientWidth, height = target.clientHeight, ratio = window.devicePixelRatio || 1;
      target.width = width * ratio; target.height = height * ratio;
      const ctx = target.getContext('2d'); ctx.scale(ratio, ratio); ctx.lineWidth = 2;
      const path = (points, color, closed=false) => {
        if (!points?.length) return; ctx.strokeStyle=color; ctx.beginPath();
        points.forEach(([x,y], i) => i ? ctx.lineTo(x*width,y*height) : ctx.moveTo(x*width,y*height));
        if (closed) ctx.closePath(); ctx.stroke();
        points.forEach(([x,y]) => {ctx.beginPath();ctx.arc(x*width,y*height,4,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();});
      };
      path(geometry.roi, '#a5b4fc', true);
      geometry.entries?.forEach(line => path(line.points, '#86efac'));
      geometry.exits?.forEach(line => path(line.points, '#fca5a5'));
      path(pending, '#fde68a');
      if (video?.available !== false) objects.forEach(item => {
        const [x1,y1,x2,y2]=item.box; ctx.strokeStyle='#86efac';ctx.strokeRect(x1*width,y1*height,(x2-x1)*width,(y2-y1)*height);
        const label=`${categories[item.category] || item.category} #${item.tracker_id}`;
        ctx.font='12px system-ui'; const textWidth=ctx.measureText(label).width;
        ctx.fillStyle='#09090b';ctx.fillRect(x1*width,Math.max(0,y1*height-18),textWidth+8,18);
        ctx.fillStyle='#f4f4f5';ctx.fillText(label,x1*width+4,Math.max(13,y1*height-4));
      });
    };
    draw(); const observer = new ResizeObserver(draw); observer.observe(target);
    return () => observer.disconnect();
  }, [geometry, pending, objects, video]);
  const move = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    dispatch(addPoint([(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height]));
  };
  return <section className="panel viewer-panel" aria-labelledby="videoHeading">
    <div className="section-head"><div><h2 id="videoHeading">Видеопоток</h2><p id="videoTitle" className="section-subtitle">{video?.name || 'Видео не выбрано'}</p></div></div>
    <div className="viewer" style={{aspectRatio:video ? `${video.width}/${video.height}` : '16/9'}}>
      {video && video.available !== false ? <video key={video.id} id="player" ref={player} src={`/api/videos/${video.id}/media?kind=file`} poster={`/api/videos/${video.id}/media?kind=frame&time_s=0`} controls={!editing} onTimeUpdate={e => setTime(e.currentTarget.currentTime)} onSeeked={e => setTime(e.currentTarget.currentTime)} onError={() => setMediaError('Не удалось воспроизвести файл. Попробуйте MP4 с кодеком H.264.')}/> : <div className="empty"><strong>{video ? 'Исходный файл недоступен' : 'Выберите видеозапись'}</strong><span>Загрузите видео через архив слева.</span></div>}
      <canvas id="overlay" ref={canvas} aria-label="Линии, область подсчёта и обнаруженные объекты" onClick={editing ? move : undefined} style={{pointerEvents:editing?'auto':'none'}}/>
    </div>
    {mediaError && <p role="alert">{mediaError}</p>}
    <div className="formrow"><span className="meta">{timeLabel(time)} / {timeLabel(video?.duration)} · {video ? `${video.width}×${video.height}` : '—'}</span>
      {editing && <button type="button" onClick={() => player.current?.paused ? player.current.play().catch(error => setMediaError(error.message)) : player.current?.pause()}>Воспроизвести / пауза</button>}</div>
    <input aria-label="Позиция видео" type="range" min="0" max={video?.duration || 1} step="0.05" value={time} disabled={!video || video.available === false} onChange={e => {const value=Number(e.target.value); if(player.current) player.current.currentTime=value;setTime(value);}}/>
    {editing && <p className="mode-info">Добавляйте точки на кадре или введите координаты в конфигурации.</p>}
  </section>;
}
