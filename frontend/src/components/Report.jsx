import {labels} from '../constants.js';
import {formatTime} from '../utils.js';
import {Cartogram, CartogramTable} from './Cartogram.jsx';

function BarList({data}) {
  if (!data.length) return <p className="list-empty">Данные появятся после обнаружения объектов.</p>;
  const max = Math.max(...data.map(item => item.count), 1);
  return data.map(item => <div className="bar-row" key={`${item.label}-${item.category}`}><div className="bar-label"><span>{item.label}</span><strong>{item.count}</strong></div><div className="bar-track"><div className={`bar-fill ${item.category}`} style={{width: `${item.count / max * 100}%`}} /></div></div>);
}

function RouteTable({rows}) {
  return <div className="tablewrap"><table><thead><tr><th>Откуда</th><th>Куда</th><th>Категория</th><th>Количество</th></tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={`${row.from}-${row.to}-${row.category}-${index}`}><td>{row.from}</td><td>{row.to}</td><td>{labels[row.category] || row.category}</td><td>{row.count}</td></tr>) : <tr><td colSpan="4">Нет учтённых проездов</td></tr>}</tbody></table></div>;
}

export function Report({traffic}) {
  const {summary, cartogram} = traffic.result || {};
  if (!summary || (['queued', 'running'].includes(traffic.run?.status) && !traffic.events.length)) return null;
  const interval = Math.max(1, Math.min(1440, Number(traffic.intervalMinutes) || 15)) * 60;
  const transport = summary.events.filter(event => event.category !== 'pedestrian').length;
  const pedestrians = summary.events.filter(event => event.category === 'pedestrian').length;
  const pending = summary.statuses.review || 0;
  const counts = new Map(); summary.events.forEach(event => counts.set(event.category, (counts.get(event.category) || 0) + 1));
  const categoryData = [...counts].sort((a, b) => b[1] - a[1]).map(([category, count]) => ({label: labels[category] || category, count, category}));
  const intervals = new Map(); summary.intervals.forEach(item => intervals.set(item.start_s, (intervals.get(item.start_s) || 0) + item.count));
  const intervalData = [...intervals].sort((a, b) => a[0] - b[0]).map(([start, count]) => ({label: `${formatTime(start)}–${formatTime(start + interval)}`, count, category: 'time'}));
  const metrics = [[summary.total, 'Всего учтено'], [transport, 'Транспорт'], [pedestrians, 'Пешеходы'], ...(pending ? [[pending, 'На проверке']] : [])];
  const note = cartogram?.topology === 'unknown'
    ? 'Тип перекрёстка не удалось определить по траекториям. Выберите трёхлучевую или пересекающуюся схему: пересчитывать видео не потребуется.'
    : cartogram ? `${cartogram.source === 'reference' ? 'Вид узла взят из схемы приложенного примера. ' : ''}Направление определено для ${cartogram.routed} из ${cartogram.total} учтённых объектов${cartogram.motion_estimated ? ` (из них ${cartogram.motion_estimated} — оценка по движению в кадре)` : ''}${cartogram.user_directions ? `; ${cartogram.user_directions} — по вашим именованным линиям` : ''}. ${cartogram.unresolved ? `Для ${cartogram.unresolved} направление не определено и на схеме не показано. ` : ''}Без пользовательских линий лучи условные, не географические направления дорог. Толщина и число на стрелке — поток, цвет — преобладающая категория; остальные категории перечислены в таблице.` : '';
  return <div id="report">
    <div className="report-head"><div><span className="eyebrow">ОБЗОР ПОТОКА</span><h3>Ключевые показатели</h3></div><span className="meta">{pending ? `${pending} событий ожидают проверки и не включены в итог` : ['queued', 'running'].includes(traffic.run.status) ? 'Предварительные результаты — анализ ещё не завершён' : 'Данные сохранены для этого анализа'}</span></div>
    <div className="summary">{metrics.map(([number, text]) => <div className="metric" key={text}><strong>{number}</strong><span>{text}</span></div>)}</div>
    <div className="charts"><div className="chart-card"><h3>По категориям</h3><div className="bar-list"><BarList data={categoryData} /></div></div><div className="chart-card"><h3>По времени</h3><div className="bar-list"><BarList data={intervalData} /></div></div></div>
    <div className="chart-card cartogram-card">
      <div className="section-head"><div><span className="eyebrow">СХЕМА ДВИЖЕНИЯ</span><h3>Картограмма направлений</h3></div><label>Вид узла<select value={traffic.cartogramTopology} onChange={event => traffic.setCartogramTopology(event.target.value)}><option value="auto">Определить, если возможно</option><option value="three_way">Трёхлучевой / треугольный</option><option value="four_way">Пересекающийся / четыре луча</option></select></label></div>
      <p className="section-subtitle" role="status">{note}</p><Cartogram data={cartogram} />{cartogram && cartogram.topology !== 'unknown' && <CartogramTable rows={cartogram.matrix} />}
    </div>
    {summary.geometry.mode !== 'automatic' && <div className="routes"><h3>Направления движения</h3><RouteTable rows={summary.matrix} /></div>}
    <div className="export-links" aria-label="Форматы экспорта"><span>Скачать отчёт</span>{['xlsx', 'csv', 'json'].map(ext => <a key={ext} className="linkbutton" href={`/api/runs/${traffic.run.id}/export/${ext}?interval=${interval}`}>{ext === 'xlsx' ? 'Excel' : ext.toUpperCase()}</a>)}</div>
    <div className="run-list-head"><div><h3>Обнаруженные события</h3><p className="section-subtitle">Исправьте класс или отклоните ошибочное обнаружение.</p></div><button type="button" onClick={() => traffic.openEvent(null)}>Добавить пропущенный объект</button></div>
    <div className="tablewrap events-table"><table><thead><tr><th>Время</th><th>Категория</th><th>Откуда</th><th>Куда</th><th>Статус</th><th>Действие</th></tr></thead><tbody>{traffic.events.length ? traffic.events.map(event => <tr key={event.id}><td>{formatTime(event.time_s)} <small>({event.time_s.toFixed(2)} с)</small></td><td>{labels[event.category] || event.category}</td><td>{event.from_direction}</td><td>{event.to_direction}</td><td><span className={`status ${event.status}`}>{labels[event.status] || event.status}</span></td><td><button type="button" onClick={() => traffic.openEvent(event)}>Править</button></td></tr>) : <tr><td colSpan="6" className="muted">Событий пока нет</td></tr>}</tbody></table></div>
  </div>;
}
