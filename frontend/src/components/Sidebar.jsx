import {InfoIcon, UploadIcon} from './Icons.jsx';
import {formatTime} from '../utils.js';

function SidebarList({items, empty, selectedId, onSelect, type}) {
  if (!items.length) return <p className="list-empty">{empty}</p>;
  return items.map(item => {
    const unavailable = type === 'video' && item.available === false;
    return <button key={item.id} type="button" onClick={() => onSelect(item.id)}
      className={`${selectedId === item.id ? 'active ' : ''}${unavailable ? 'unavailable' : ''}`}
      aria-pressed={selectedId === item.id}>
      <strong>{item.name}</strong>
      <small>{type === 'video'
        ? `${formatTime(item.duration)} · ${item.width}×${item.height}${unavailable ? ' · источник недоступен' : ''}`
        : 'Пользовательская зона'}</small>
    </button>;
  });
}

export function Sidebar({traffic}) {
  const uploading = traffic.busy === 'upload';
  return <aside className="sidebar" aria-label="Видеозаписи и зоны подсчёта">
    <div className="sidebar-intro">
      <span className="eyebrow">РАБОЧЕЕ ПРОСТРАНСТВО</span>
      <p className="sidebar-title">Движение под контролем</p>
      <p>Загрузите запись, выберите способ подсчёта и получите проверяемый отчёт.</p>
    </div>
    <label className={`upload${uploading ? ' is-loading' : ''}`} aria-busy={uploading || undefined}>
      <UploadIcon />
      <span><strong>Загрузить видео</strong><small>Выбрать файл на устройстве</small></span>
      <input type="file" accept=".mp4,.mov,.mkv,.avi,.webm,video/*" disabled={uploading}
        aria-describedby="uploadStatus" onChange={event => {
          const file = event.target.files?.[0];
          traffic.uploadVideo(file);
          event.target.value = '';
        }} />
    </label>
    <p id="uploadStatus" className="sidebar-hint" role="status" aria-live="polite">{traffic.uploadStatus}</p>
    <div className="sidebar-section">
      <div className="sidebar-section-head"><span className="sidebar-heading">Видеозаписи</span><span aria-hidden="true">01</span></div>
      <div className="list" aria-label="Видеозаписи" aria-live="polite">
        <SidebarList items={traffic.videos} empty="Пока нет записей" selectedId={traffic.video?.id} onSelect={traffic.selectVideo} type="video" />
      </div>
    </div>
    <div className="sidebar-section">
      <div className="sidebar-section-head"><span className="sidebar-heading">Сохранённые зоны</span><span aria-hidden="true">02</span></div>
      <div className="list" aria-label="Зоны подсчёта" aria-live="polite">
        <SidebarList items={traffic.scenes} empty={traffic.video ? 'Можно обойтись без разметки' : 'Выберите видео'} selectedId={traffic.scene?.id} onSelect={traffic.selectScene} type="scene" />
      </div>
    </div>
    <div className="aside-note"><InfoIcon /><p>Для анализа нужны веса YOLO и запущенный worker. Все результаты сохраняются локально.</p></div>
  </aside>;
}
