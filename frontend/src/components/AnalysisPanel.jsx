import {activeRunStatuses, runLabels} from '../constants.js';
import {Report} from './Report.jsx';

function RunStatus({run, video}) {
  if (!run) return <div className="run-status" data-status="idle" role="status" aria-live="polite">{video ? 'Готово к запуску. Разметка для автоматического анализа не нужна.' : 'Выберите запись и запустите анализ.'}</div>;
  const progress = Math.max(0, Math.min(100, Math.round((run.progress || 0) * 100)));
  const eta = run.status === 'running' && Number.isFinite(run.eta_s) ? `Ориентировочно осталось ${Math.max(1, Math.ceil(run.eta_s / 60))} мин.` : '';
  return <div className="run-status" data-status={run.status} role="status" aria-live="polite"><div className="run-status-line"><strong>{runLabels[run.status] || run.status}</strong><span>{progress}%</span></div><div className="progress-track" role="progressbar" aria-label="Прогресс анализа" aria-valuemin="0" aria-valuemax="100" aria-valuenow={progress}><div style={{width: `${progress}%`}} /></div>{eta && <small>{eta}</small>}{run.message && <small>{run.message}</small>}</div>;
}

export function AnalysisPanel({traffic}) {
  return <section className="panel analysis-panel" aria-labelledby="analysisHeading">
    <div className="section-head"><div className="section-title"><span className="step-badge" aria-hidden="true">03</span><div><span className="eyebrow">ОБРАБОТКА И ОТЧЁТ</span><h2 id="analysisHeading">Результаты анализа</h2><p className="section-subtitle">Подсчёт, категории и события сохраняются отдельно для каждого запуска.</p></div></div><button type="button" className={`primary action${traffic.busy === 'analyze' ? ' is-loading' : ''}`} disabled={!traffic.video || traffic.video.available === false || traffic.busy === 'analyze'} onClick={traffic.analyze}>{traffic.busy === 'analyze' ? 'Запускаем' : 'Запустить анализ'}</button></div>
    <div className="formrow settings">
      <label>Режим обработки<select value={traffic.profile} onChange={event => traffic.setProfile(event.target.value)}><option value="fast">Быстрый · YOLO11s</option><option value="ensemble">Ансамбль · две YOLO · каждый кадр</option></select></label>
      {traffic.profile === 'fast' && <label>Кадров/с в быстром режиме<input type="number" min="2" max="12" step="1" value={traffic.sampleFps} inputMode="numeric" onChange={event => traffic.setSampleFps(event.target.value)} /></label>}
      <label>Схема перекрёстка<select value={traffic.topology} onChange={event => traffic.setTopology(event.target.value)}><option value="auto">Определить, если возможно</option><option value="three_way">Трёхлучевой / треугольный</option><option value="four_way">Пересекающийся / четыре луча</option></select></label>
      <label>Интервал графика, мин<input type="number" min="1" max="1440" value={traffic.intervalMinutes} inputMode="numeric" onChange={event => traffic.setIntervalMinutes(event.target.value)} /></label>
      <button type="button" className={traffic.busy === 'refresh' ? 'is-loading' : ''} disabled={traffic.busy === 'refresh'} onClick={traffic.refresh}>{traffic.busy === 'refresh' ? 'Обновляем' : 'Обновить результаты'}</button>
    </div>
    <RunStatus run={traffic.run} video={traffic.video} />
    <div className="run-list-head"><h3>История анализов</h3>{traffic.run && activeRunStatuses.includes(traffic.run.status) && <button type="button" className={`danger-button${traffic.busy === 'cancel' ? ' is-loading' : ''}`} disabled={traffic.busy === 'cancel'} onClick={traffic.cancelRun}>{traffic.busy === 'cancel' ? 'Останавливаем' : 'Остановить анализ'}</button>}</div>
    <div className="list run-list" aria-live="polite">{traffic.runs.length ? traffic.runs.map(run => <button key={run.id} type="button" className={traffic.run?.id === run.id ? 'active' : ''} aria-pressed={traffic.run?.id === run.id} onClick={() => traffic.selectRun(run.id)}><strong>{runLabels[run.status] || run.status} · {Math.round((run.progress || 0) * 100)}%</strong><small>{new Date(run.created_at).toLocaleString('ru-RU')} {run.message ? `· ${run.message}` : ''}</small></button>) : <p className="list-empty">Первый анализ появится здесь</p>}</div>
    <Report traffic={traffic} />
  </section>;
}
