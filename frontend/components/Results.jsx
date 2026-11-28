import React, {useState} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {api, categories, jsonRequest, statuses, timeLabel} from '../api';
import {runWorkspaceAction} from '../store/workspaceActions.js';
import {
  intervalChanged, refreshRequested, runSelected, selectBusy, selectInterval, selectResult,
  selectRun, selectRunId, selectRuns, selectVideoId,
} from '../store/workspaceSlice.js';
import {EventEditor} from './EventEditor';
const palette=['#a5b4fc','#86efac','#fca5a5','#7dd3fc','#fde68a','#f0abfc'];
function Bars({rows,label}) {
  const max=Math.max(1,...rows.map(row=>row.count));
  return <div className="bar-list" aria-label={label}>{rows.length?rows.map((row,index)=><div className="result-bar" key={index}><span>{row.label}</span><div className="bar-track"><span style={{width:`${100*row.count/max}%`,background:palette[index%palette.length]}}/></div><strong>{row.count}</strong></div>):<p className="meta">Пока нет учтённых событий.</p>}</div>;
}
function Clusters({data}) {
  return <section className="result-section"><h3>Кластеры направлений</h3><p className="mode-info">Траектории в координатах кадра. Номера кластеров относятся только к этому запуску, без привязки к сторонам света.</p>
    {data?.clusters?.length ? <><svg className="cluster-map" viewBox="0 0 600 338" role="img" aria-label="Средние траектории кластеров">{data.clusters.map((cluster,index)=><g key={cluster.id} fill="none" stroke={palette[index%palette.length]} strokeWidth="3"><polyline points={cluster.polyline.map(([x,y])=>`${x*600},${y*338}`).join(' ')}/><circle cx={cluster.polyline[0][0]*600} cy={cluster.polyline[0][1]*338} r="5"/><text stroke="none" fill={palette[index%palette.length]} x={cluster.polyline.at(-1)[0]*600} y={cluster.polyline.at(-1)[1]*338}>→ {cluster.id}</text></g>)}</svg>
    <div className="tablewrap"><table><thead><tr><th>Кластер</th><th>Категория</th><th>Учтено</th></tr></thead><tbody>{data.counts.map(row=><tr key={`${row.cluster}-${row.category}`}><td>{row.cluster}</td><td>{categories[row.category]}</td><td>{row.count}</td></tr>)}</tbody></table></div></>:<p>Для устойчивого кластера нужны минимум три похожие движущиеся траектории.</p>}
    <p className="meta">События без устойчивого кластера: {data?.unresolved_events || 0}</p></section>;
}
function Cartogram({diagram}) {
  const coords=diagram.topology==='three_way'?{'Север':[150,35],'Юго-восток':[260,220],'Юго-запад':[40,220]}:{'Север':[150,25],'Восток':[270,125],'Юг':[150,235],'Запад':[30,125]};
  if(diagram.topology==='unknown') return <p className="mode-info">Недостаточно данных для схемы перекрёстка. Выберите тип узла, если он известен.</p>;
  return <svg className="cartogram-svg" viewBox="0 0 300 260" role="img" aria-label="Картограмма направлений">{diagram.arms.map(arm=><g key={arm}><line x1="150" y1="125" x2={coords[arm][0]} y2={coords[arm][1]} stroke="#3f3f46" strokeWidth="24"/><text x={coords[arm][0]} y={coords[arm][1]-10} textAnchor="middle" fill="#f4f4f5" fontSize="11">{arm}</text></g>)}{diagram.matrix.map((row,index)=>coords[row.from]&&coords[row.to]?<path key={index} d={`M${coords[row.from].join(',')} Q150,125 ${coords[row.to].join(',')}`} fill="none" stroke={palette[index%palette.length]} strokeWidth={Math.min(8,1+Math.log2(row.count+1))}><title>{row.from} → {row.to}: {row.count} {categories[row.category]}</title></path>:null)}</svg>;
}
export function Results() {
  const dispatch = useDispatch();
  const videoId = useSelector(selectVideoId);
  const runId = useSelector(selectRunId);
  const run = useSelector(selectRun);
  const runs = useSelector(selectRuns);
  const interval = useSelector(selectInterval);
  const busy = useSelector(selectBusy);
  const data = useSelector(selectResult);
  const summary = data?.summary;
  const [edit,setEdit]=useState(undefined),[reference,setReference]=useState(''),[metrics,setMetrics]=useState(null),[metricError,setMetricError]=useState('');

  const refresh = () => dispatch(refreshRequested());
  const act = action => dispatch(runWorkspaceAction(action));
  const updateRun = payload => act(async () => {
    await api(`/api/runs/${runId}`, jsonRequest('PATCH', payload));
    refresh();
  });
  async function evaluate(file) {
    if(!file)return;setMetrics(null);setMetricError('');
    await act(async () => {
      try {
        const body = new FormData();
        body.append('file', file);
        const uploaded = await api(`/api/videos/${videoId}/ground-truth`, {method:'POST', body});
        setReference(file.name);
        setMetrics(await api(`/api/runs/${runId}/evaluate/${uploaded.id}`));
      } catch (error) {
        setMetricError(error.message);
        throw error;
      }
    });
  }
  return <section className="panel analysis-panel" aria-labelledby="analysisHeading"><h2 id="analysisHeading">Анализ и отчёт</h2>
    <div id="runStatus" role="status" aria-live="polite">{run?`${statuses[run.status]} · ${Math.round(run.progress*100)}% · ${run.message||''}`:'Выберите запись и запустите анализ.'}</div>
    {run&&['queued','running','stalled'].includes(run.status)&&<><progress max="1" value={run.progress} aria-label="Прогресс анализа"/><button id="cancelRun" disabled={busy} onClick={()=>updateRun({action:'cancel'})}>Остановить анализ</button></>}
    <div id="runs" className="list run-list">{runs.map(item=><button key={item.id} data-id={item.id} aria-pressed={runId===item.id} onClick={()=>dispatch(runSelected(item.id))}><strong>{statuses[item.status]}</strong><small>{new Date(item.created_at).toLocaleString('ru-RU')}</small></button>)}</div>
    {summary&&<div id="report"><div className="summary">{[['Всего',summary.total],['Транспорт',summary.transport_total],['Пешеходы',summary.pedestrian_total]].map(([label,value])=><div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
      <div className="formrow"><label>Интервал графика, мин<input id="interval" type="number" min="1" max="1440" value={interval/60} onChange={e=>{const n=Number(e.target.value);if(n>=1&&n<=1440)dispatch(intervalChanged(n*60));}}/></label><button id="refresh" onClick={refresh}>Обновить результаты</button></div>
      <div className="charts"><section><h3>По категориям</h3><Bars rows={summary.category_totals.map(row=>({...row,label:categories[row.category]}))}/></section><section><h3>По времени</h3><Bars rows={summary.intervals.map(row=>({...row,label:`${timeLabel(row.start_s)} · ${categories[row.category]}`}))}/></section></div>
      <section className="result-section"><h3>Картограмма</h3><label>Вид узла<select value={data.cartogram.preference||'auto'} onChange={e=>updateRun({action:'set_topology',topology:e.target.value})}><option value="auto">Автоматически</option><option value="three_way">Три луча</option><option value="four_way">Четыре луча</option></select></label><Cartogram diagram={data.cartogram}/><p className="meta">Направление определено: {data.cartogram.routed}; не определено: {data.cartogram.unresolved}. Схема условная.</p><div className="tablewrap"><table><thead><tr><th>Откуда</th><th>Куда</th><th>Категория</th><th>Количество</th></tr></thead><tbody>{(data.cartogram.matrix.length?data.cartogram.matrix:summary.matrix).map((row,i)=><tr key={i}><td>{row.from}</td><td>{row.to}</td><td>{categories[row.category]}</td><td>{row.count}</td></tr>)}</tbody></table></div></section>
      <Clusters data={data.clusters}/>
      {data.performance&&<p className="mode-info">Обработано {data.performance.processed_frames} кадров за {data.performance.elapsed_s.toFixed(1)} с; {data.performance.inference_fps.toFixed(1)} кадр/с. Ночная коррекция: {data.performance.enhanced_frames} кадров.</p>}
      <div className="export-links"><span>Скачать отчёт</span>{['xlsx','csv','json'].map(format=><a id={format} className="linkbutton" key={format} href={`/api/runs/${runId}/export/${format}?interval=${interval}`}>{format.toUpperCase()}</a>)}</div>
      <div className="section-head"><h3>События</h3><button id="manual" onClick={()=>setEdit(null)}>Добавить пропущенный объект</button></div>
      <div className="tablewrap events-table"><table><thead><tr><th>Время</th><th>Категория</th><th>Откуда → куда</th><th>Статус</th><th>Действие</th></tr></thead><tbody id="events">{data.events.map(event=><tr key={event.id}><td>{timeLabel(event.time_s)}</td><td>{categories[event.category]}</td><td>{event.from_direction} → {event.to_direction}</td><td>{statuses[event.status]}</td><td><button onClick={()=>setEdit(event)}>Проверить</button></td></tr>)}</tbody></table></div>
      <section className="result-section"><h3>Проверка по эталону</h3><p className="mode-info">Загрузите разметку: JSON с frames для Precision, Recall, F1, MOTA и IDF1; таблицу from/to/category/count для MAE, RMSE и WAPE. Для кадров нужны точные временные метки анализа.</p><label>Эталон JSON, CSV или XLSX<input type="file" accept=".json,.csv,.xlsx" disabled={busy||run?.status!=='completed'} onChange={e=>evaluate(e.target.files[0])}/></label>{metricError&&<p role="alert">{metricError}</p>}{metrics&&<><p>{reference}</p><dl className="metrics-list">{Object.entries(metrics).filter(([key,value])=>key!=='rows'&&typeof value!=='object').map(([key,value])=><div key={key}><dt>{key}</dt><dd>{typeof value==='number'?Number(value.toFixed(4)):String(value)}</dd></div>)}</dl><p className="meta">Метрики относятся только к загруженному эталону.</p></>}</section>
    </div>}
    {summary&&edit!==undefined&&<EventEditor key={edit?.id||'new'} event={edit} geometry={summary.geometry} onClose={()=>setEdit(undefined)}/>}
  </section>;
}
