import {useEffect, useState} from 'react';
import {useOverlayCanvas} from '../hooks/useOverlayCanvas.js';
import {formatTime} from '../utils.js';
import {VideoIcon} from './Icons.jsx';

export function VideoPanel({traffic}) {
  const {canvasRef, draw} = useOverlayCanvas({traffic});
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const available = traffic.video?.available !== false;
  const duration = traffic.video?.duration || 0;
  useEffect(() => { setCurrentTime(0); setPlaying(false); }, [traffic.video?.id]);
  const hint = traffic.view === 'analysis'
    ? ['queued', 'running'].includes(traffic.run?.status) ? 'Рамки появятся после завершения обработки.' : 'Рамки соответствуют обнаружениям выбранного анализа; линии — сохранённой для него зоне.'
    : traffic.mode === 'manual' ? 'Нажимайте на видео, чтобы поставить точки, или введите координаты ниже.' : 'После анализа здесь появятся рамки обнаруженных объектов.';
  return <section className="panel viewer-panel" aria-labelledby="videoHeading">
    <div className="section-head"><div className="section-title"><span className="step-badge" aria-hidden="true">01</span><div><span className="eyebrow">ИСТОЧНИК</span><h2 id="videoHeading">Видеозапись</h2><p className="section-subtitle">{traffic.video?.name || 'Выберите или загрузите видеозапись'}</p></div></div><span className="meta">{traffic.video ? `${traffic.video.width}×${traffic.video.height} · ${formatTime(duration)}` : ''}</span></div>
    <div className="viewer" style={traffic.video ? {aspectRatio: `${traffic.video.width}/${traffic.video.height}`} : undefined}>
      <video ref={node => { traffic.videoRef.current = node; }} controls playsInline preload="metadata" aria-label="Видеозапись для анализа"
        src={traffic.video && available ? `/api/videos/${traffic.video.id}/media?kind=file` : undefined}
        poster={traffic.video && available ? `/api/videos/${traffic.video.id}/media?kind=frame&time_s=0` : undefined}
        onTimeUpdate={event => { setCurrentTime(event.currentTarget.currentTime); traffic.loadDetections(); }}
        onSeeked={() => traffic.loadDetections(true)} onLoadedMetadata={draw}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)}
        onError={event => event.currentTarget.getAttribute('src') && traffic.refresh()} />
      <canvas ref={canvasRef} className={traffic.mode === 'manual' && traffic.view === 'setup' ? 'editing' : ''}
        role="img" aria-label="Линии подсчёта и обнаруженные объекты" aria-describedby="overlayHint"
        onClick={event => {
          if (traffic.view !== 'setup' || traffic.mode !== 'manual' || !traffic.video) return;
          const rect = event.currentTarget.getBoundingClientRect();
          traffic.addPoint([(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height]);
        }} />
      {(!traffic.video || !available) && <div className="empty"><span className="empty-mark" aria-hidden="true"><VideoIcon /></span><strong>{traffic.video ? 'Исходный файл недоступен' : 'Здесь появится видео'}</strong><span>{traffic.video ? 'Сохранённые результаты можно просмотреть, но для нового анализа загрузите видео снова' : 'Выберите запись в панели слева, чтобы начать'}</span></div>}
    </div>
    <div className="timeline">
      <button type="button" aria-label={playing ? 'Приостановить видео' : 'Воспроизвести видео'} disabled={!traffic.video || !available}
        onClick={() => playing ? traffic.videoRef.current?.pause() : traffic.videoRef.current?.play()}>{playing ? 'Пауза' : 'Воспроизвести'}</button>
      <label htmlFor="scrub">Позиция видео</label>
      <input type="range" min="0" max={duration} step="0.1" value={currentTime} id="scrub" aria-label="Позиция видео"
        onChange={event => { const value = Number(event.target.value); setCurrentTime(value); if (traffic.videoRef.current) traffic.videoRef.current.currentTime = value; traffic.loadDetections(true); }} />
      <output htmlFor="scrub">{formatTime(currentTime)}</output>
    </div>
    <p id="overlayHint" className="viewer-caption">{hint}</p>
  </section>;
}
