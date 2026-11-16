import {useEffect, useRef, useState} from 'react';

export function EventDialog({traffic}) {
  const dialogRef = useRef(null);
  const [form, setForm] = useState(null);
  useEffect(() => {
    if (traffic.dialogEvent === undefined) { dialogRef.current?.close(); return; }
    const event = traffic.dialogEvent;
    const savedGeometry = traffic.run ? JSON.parse(traffic.run.geometry) : {mode: 'automatic', entries: [], exits: []};
    const auto = savedGeometry.mode === 'automatic';
    setForm({id: event?.id || '', version: event?.version || '', time_s: event?.time_s ?? Number(traffic.videoRef.current?.currentTime || 0).toFixed(2), category: event?.category || 'car', from_direction: event?.from_direction || (auto ? 'В кадре' : savedGeometry.entries[0]?.name || ''), to_direction: event?.to_direction || (auto ? 'В кадре' : savedGeometry.exits[0]?.name || ''), status: event?.status || 'confirmed', reason: ''});
    if (!dialogRef.current?.open) dialogRef.current?.showModal();
  }, [traffic.dialogEvent, traffic.run, traffic.videoRef]);
  if (!form) return <dialog ref={dialogRef} aria-labelledby="dialogTitle" />;
  const savedGeometry = traffic.run ? JSON.parse(traffic.run.geometry) : {mode: 'automatic', entries: [], exits: []};
  const auto = savedGeometry.mode === 'automatic';
  const update = (key, value) => setForm(current => ({...current, [key]: value}));
  return <dialog ref={dialogRef} aria-labelledby="dialogTitle" onCancel={event => { event.preventDefault(); traffic.closeEvent(); }}>
    <form method="dialog" onSubmit={event => { event.preventDefault(); const payload = {...form, time_s: Number(form.time_s)}; if (payload.id) payload.version = Number(payload.version); else { delete payload.id; delete payload.version; } traffic.saveEvent(payload); }}>
      <div className="dialog-head"><span className="eyebrow">КОРРЕКТИРОВКА ДАННЫХ</span><h2 id="dialogTitle">{form.id ? 'Правка события' : 'Добавить пропущенный объект'}</h2><p>Проверьте параметры обнаруженного объекта перед сохранением.</p></div>
      <div className="grid2">
        <label>Время, сек<input type="number" step="0.01" min="0" required value={form.time_s} onChange={event => update('time_s', event.target.value)} /></label>
        <label>Категория<select value={form.category} onChange={event => update('category', event.target.value)}><option value="car">Легковой автомобиль</option><option value="truck">Грузовой автомобиль</option><option value="bus">Автобус</option><option value="motorcycle">Мотоцикл</option><option value="bicycle">Велосипед</option><option value="pedestrian">Пешеход</option></select></label>
        <label>Откуда<select value={form.from_direction} onChange={event => update('from_direction', event.target.value)}>{(auto ? ['В кадре'] : savedGeometry.entries.map(item => item.name)).map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Куда<select value={form.to_direction} onChange={event => update('to_direction', event.target.value)}>{(auto ? ['В кадре'] : savedGeometry.exits.map(item => item.name)).map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Статус<select value={form.status} onChange={event => update('status', event.target.value)}><option value="confirmed">Подтверждено</option><option value="review">Проверить</option><option value="auto_accept">Принять автоматически</option><option value="discarded">Отклонено</option></select></label>
        <label>Причина<input placeholder="Комментарий к правке" value={form.reason} onChange={event => update('reason', event.target.value)} /></label>
      </div>
      <menu><button type="button" onClick={traffic.closeEvent}>Отмена</button><button className={`primary${traffic.busy === 'event' ? ' is-loading' : ''}`} disabled={traffic.busy === 'event'}>{traffic.busy === 'event' ? 'Сохраняем' : 'Сохранить'}</button></menu>
    </form>
  </dialog>;
}
