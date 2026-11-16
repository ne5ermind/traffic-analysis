import {LogoIcon} from './Icons.jsx';

export function Topbar() {
  return <header className="topbar">
    <div className="brand">
      <span className="logo" aria-hidden="true"><LogoIcon /></span>
      <div><strong>InnovaTransport</strong><small>Аналитика транспортных потоков</small></div>
    </div>
    <div className="topbar-actions" aria-label="Состояние системы">
      <span className="system-badge"><span className="status-dot" aria-hidden="true" />Локальный контур</span>
      <span className="privacy">Видео не покидает устройство</span>
    </div>
  </header>;
}
