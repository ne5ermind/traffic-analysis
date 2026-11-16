import {useState} from 'react';

function GeometryChips({traffic}) {
  const parts = [
    ...traffic.geometry.entries.map((item, index) => ({kind: 'entries', index, text: `Въезд: ${item.name}`})),
    ...traffic.geometry.exits.map((item, index) => ({kind: 'exits', index, text: `Выезд: ${item.name}`})),
  ];
  if (traffic.geometry.roi?.length) parts.push({kind: 'roi', index: 0, text: `Область (${traffic.geometry.roi.length} точек)`});
  if (!parts.length) return <span className="list-empty">Линии ещё не заданы</span>;
  return parts.map(part => <span className="chip" key={`${part.kind}-${part.index}`}>{part.text}<button type="button" aria-label={`Удалить ${part.text}`} onClick={() => traffic.removeGeometry(part.kind, part.index)}>×</button></span>);
}

export function CountingPanel({traffic}) {
  const [point, setPoint] = useState({x: 50, y: 50});
  const automaticText = traffic.profile === 'fast'
    ? 'Быстрый режим: одна YOLO11s обрабатывает выбранную частоту кадров (по умолчанию 6 кадров/с), ByteTrack связывает объекты между кадрами. Учитываются пешеходы, велосипеды, легковые автомобили, мотоциклы, автобусы и грузовики. При понижении частоты можно пропустить быстрые объекты.'
    : 'Ансамбль: YOLO11m и YOLOv10m с объединением рамок и ByteTrack обрабатывают каждый кадр. Этот режим значительно медленнее быстрого.';
  const addCoordinates = () => {
    const x = Number(point.x), y = Number(point.y);
    if (![x, y].every(value => Number.isFinite(value) && value >= 0 && value <= 100)) return;
    traffic.addPoint([x / 100, y / 100]);
  };
  return <section className="panel" aria-labelledby="zoneHeading">
    <div className="section-head"><div className="section-title"><span className="step-badge" aria-hidden="true">02</span><div><span className="eyebrow">ПАРАМЕТРЫ ПОДСЧЁТА</span><h2 id="zoneHeading">Как считать объекты?</h2><p className="section-subtitle">Автоматический режим готов к запуску без разметки.</p></div></div></div>
    <div className="mode-switch" role="group" aria-label="Режим подсчёта">
      <button type="button" className={traffic.mode === 'automatic' ? 'selected' : ''} aria-pressed={traffic.mode === 'automatic'} onClick={() => traffic.changeMode('automatic')}><span className="mode-kicker">БЕЗ РАЗМЕТКИ</span><strong>Автоматически</strong><span>Каждый устойчивый трек один раз за анализ</span></button>
      <button type="button" className={traffic.mode === 'manual' ? 'selected' : ''} aria-pressed={traffic.mode === 'manual'} onClick={() => traffic.changeMode('manual')}><span className="mode-kicker">ТОЧНАЯ ЗОНА</span><strong>По моей зоне</strong><span>Подсчёт проездов после пересечения линий</span></button>
    </div>
    {traffic.mode === 'automatic' && <p className="mode-info" aria-live="polite">{automaticText}</p>}
    {traffic.mode === 'manual' && <div className="manual-config">
      <p className="mode-info">Поставьте по две точки для линии въезда и выезда на видео. При необходимости добавьте область интереса и сохраните зону перед анализом.</p>
      <div className="toolbar" role="group" aria-label="Инструмент разметки">
        {[['entry', 'Линия въезда'], ['exit', 'Линия выезда'], ['roi', 'Область']].map(([value, text]) => <button key={value} type="button" className={traffic.tool === value ? 'selected' : ''} aria-pressed={traffic.tool === value} onClick={() => traffic.setTool(value)}>{text}</button>)}
        <button type="button" onClick={traffic.finishRoi}>Завершить область</button><button type="button" onClick={traffic.undoPoint}>Отменить точку</button>
      </div>
      <div className="formrow point-row">
        <label>X, %<input type="number" min="0" max="100" step="0.1" value={point.x} inputMode="decimal" onChange={event => setPoint({...point, x: event.target.value})} /></label>
        <label>Y, %<input type="number" min="0" max="100" step="0.1" value={point.y} inputMode="decimal" onChange={event => setPoint({...point, y: event.target.value})} /></label>
        <button type="button" onClick={addCoordinates}>Добавить точку по координатам</button>
      </div>
      <div className="formrow">
        <label>Имя линии<input placeholder="Например, Север" value={traffic.lineName} onChange={event => traffic.setLineName(event.target.value)} /></label>
        <label>Название зоны<input value={traffic.sceneName} onChange={event => traffic.setSceneName(event.target.value)} /></label>
        <button type="button" className={`primary${traffic.busy === 'scene' ? ' is-loading' : ''}`} disabled={traffic.busy === 'scene'} onClick={traffic.saveScene}>{traffic.busy === 'scene' ? 'Сохраняем' : 'Сохранить зону'}</button>
      </div>
      <label className="zone-select">Сохранённая зона<select value={traffic.scene?.id || ''} onChange={event => traffic.selectScene(event.target.value)}><option value="">Новая зона</option>{traffic.scenes.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
      <div className="chips" aria-live="polite"><GeometryChips traffic={traffic} /></div>
    </div>}
  </section>;
}
