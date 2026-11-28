import React from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {api, timeLabel} from '../api';
import {openVideo, runWorkspaceAction} from '../store/workspaceActions.js';
import {loadVideos, noticeChanged, selectBusy, selectVideoId, selectVideos} from '../store/workspaceSlice.js';

export function Sidebar() {
  const dispatch = useDispatch();
  const videos = useSelector(selectVideos);
  const videoId = useSelector(selectVideoId);
  const busy = useSelector(selectBusy);

  async function upload(event) {
    const file = event.target.files[0]; if (!file) return;
    await dispatch(runWorkspaceAction(async dispatch => {
      const data = new FormData(); data.append('file', file);
      const video = await api('/api/videos', {method:'POST', body:data});
      await dispatch(loadVideos()).unwrap();
      dispatch(openVideo(video.id));
      dispatch(noticeChanged('Видео загружено. Можно настроить и запустить анализ.'));
    }));
    event.target.value = '';
  }
  return <aside className="sidebar" aria-label="Архив видео">
    <h2>Архив видео <span className="archive-count">{videos.length}</span></h2>
    <label className="upload"><strong>{busy ? 'Подождите…' : 'Загрузить видео'}</strong>
      <input id="upload" aria-label="Загрузить видео" type="file" accept=".mp4,.mov,.mkv,.avi,.webm" disabled={busy} onChange={upload}/></label>
    <p className="sidebar-hint">MP4, MOV, MKV, AVI или WebM. Обработка выполняется локально.</p>
    <div className="tablewrap"><table className="archive-table"><thead><tr><th>Файл</th><th>Параметры</th></tr></thead>
      <tbody id="videos">{videos.map(video => <tr key={video.id} className={videoId === video.id ? 'active' : ''}>
        <td><button data-id={video.id} aria-pressed={videoId === video.id} onClick={() => dispatch(openVideo(video.id))}>{video.name}</button><small>{new Date(video.created_at).toLocaleString('ru-RU')}</small>{video.available === false && <small>Исходный файл недоступен</small>}</td>
        <td><small>{video.width}×{video.height}<br/>{timeLabel(video.duration)} · {Number(video.fps).toFixed(1)} fps</small></td>
      </tr>)}{!videos.length && <tr><td colSpan="2">Загрузите первую запись для анализа.</td></tr>}</tbody></table></div>
    <p className="sidebar-hint">Выбор записи открывает сохранённые зоны и историю её анализов.</p>
  </aside>;
}
