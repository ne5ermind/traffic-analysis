import React from 'react';
import {api, timeLabel} from '../api';
export function Sidebar({workspace:w}) {
  async function upload(event) {
    const file = event.target.files[0]; if (!file) return;
    await w.act(async () => {
      const data = new FormData(); data.append('file', file);
      const video = await api('/api/videos', {method:'POST', body:data});
      await w.loadVideos(); w.selectVideo(video.id); w.setNotice('Видео загружено. Можно настроить и запустить анализ.');
    });
    event.target.value = '';
  }
  return <aside className="sidebar" aria-label="Архив видео">
    <h2>Архив видео <span className="archive-count">{w.videos.length}</span></h2>
    <label className="upload"><strong>{w.busy ? 'Подождите…' : 'Загрузить видео'}</strong>
      <input id="upload" aria-label="Загрузить видео" type="file" accept=".mp4,.mov,.mkv,.avi,.webm" disabled={w.busy} onChange={upload}/></label>
    <p className="sidebar-hint">MP4, MOV, MKV, AVI или WebM. Обработка выполняется локально.</p>
    <div className="tablewrap"><table className="archive-table"><thead><tr><th>Файл</th><th>Параметры</th></tr></thead>
      <tbody id="videos">{w.videos.map(video => <tr key={video.id} className={w.videoId === video.id ? 'active' : ''}>
        <td><button data-id={video.id} aria-pressed={w.videoId === video.id} onClick={() => w.selectVideo(video.id)}>{video.name}</button><small>{new Date(video.created_at).toLocaleString('ru-RU')}</small>{video.available === false && <small>Исходный файл недоступен</small>}</td>
        <td><small>{video.width}×{video.height}<br/>{timeLabel(video.duration)} · {Number(video.fps).toFixed(1)} fps</small></td>
      </tr>)}{!w.videos.length && <tr><td colSpan="2">Загрузите первую запись для анализа.</td></tr>}</tbody></table></div>
    <p className="sidebar-hint">Выбор записи открывает сохранённые зоны и историю её анализов.</p>
  </aside>;
}
