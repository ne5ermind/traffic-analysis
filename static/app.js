const $ = id => document.getElementById(id);
const blankGeometry = () => ({entries: [], exits: [], roi: []});
const state = {videos: [], scenes: [], runs: [], events: [], video: null, scene: null, run: null,
  mode: 'automatic', view: 'setup', tool: 'entry', geometry: blankGeometry(), pending: [],
  dirty: false, detections: [], request: 0, lastDetection: 0};
const labels = {car: 'Легковой автомобиль', truck: 'Грузовой автомобиль', bus: 'Автобус',
  motorcycle: 'Мотоцикл', bicycle: 'Велосипед', pedestrian: 'Пешеход',
  review: 'Проверить', confirmed: 'Подтверждено', auto_accept: 'Учтено', discarded: 'Отклонено'};
const runLabels = {queued: 'В очереди', running: 'Идёт анализ', completed: 'Завершён',
  failed: 'Ошибка', cancelled: 'Остановлен', stalled: 'Worker не отвечает'};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const formatTime = s => {const n = Math.max(0, Math.floor(Number(s) || 0));
  return `${Math.floor(n / 60)}:${String(n % 60).padStart(2, '0')}`};
let noticeTimer;
function flash(message, ok = false) {
  clearTimeout(noticeTimer);
  $('notice').textContent = message;
  $('notice').className = `notice${ok ? ' ok' : ''}`;
  $('notice').hidden = false;
  noticeTimer = setTimeout(() => $('notice').hidden = true, 7000);
}
async function api(url, options = {}) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw Error('Нет связи с локальным сервером. Проверьте, что приложение запущено.');
  }
  if (!response.ok) {
    let body; try {body = await response.json()} catch {body = {detail: response.statusText}}
    throw Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail));
  }
  return response.json();
}
async function guard(action) {try {await action()} catch (error) {flash(error.message || String(error))}}
function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.idleLabel = button.textContent;
    if (label) button.textContent = label;
    button.classList.add('is-loading');
    button.setAttribute('aria-busy', 'true');
    button.disabled = true;
  } else {
    if (button.dataset.idleLabel) button.textContent = button.dataset.idleLabel;
    delete button.dataset.idleLabel;
    button.classList.remove('is-loading');
    button.removeAttribute('aria-busy');
    button.disabled = false;
  }
}

async function loadVideos() {
  $('videos').setAttribute('aria-busy', 'true');
  state.videos = await api('/api/videos');
  $('videos').innerHTML = state.videos.map(video => {
    const unavailable = video.available === false;
    return `<button type="button" data-id="${video.id}" class="${state.video?.id === video.id ? 'active ' : ''}${unavailable ? 'unavailable' : ''}" aria-pressed="${state.video?.id === video.id}"><strong>${esc(video.name)}</strong><small>${formatTime(video.duration)} · ${video.width}×${video.height}${unavailable ? ' · источник недоступен' : ''}</small></button>`;
  }).join('') || '<p class="list-empty">Пока нет записей</p>';
  $('videos').querySelectorAll('button').forEach(button => button.onclick = () => guard(() => selectVideo(button.dataset.id)));
  $('videos').removeAttribute('aria-busy');
}
async function selectVideo(id) {
  state.video = state.videos.find(video => video.id === id);
  if (!state.video) return;
  state.scene = state.run = null;
  state.geometry = blankGeometry(); state.pending = []; state.detections = [];
  state.dirty = false; state.view = 'setup'; state.request++;
  $('topology').value = 'auto';
  $('sceneName').value = 'Моя зона';
  renderMode('automatic');
  $('videoTitle').textContent = state.video.name;
  $('videoMeta').textContent = `${state.video.width}×${state.video.height} · ${formatTime(state.video.duration)}`;
  document.querySelector('.viewer').style.aspectRatio = `${state.video.width}/${state.video.height}`;
  const available = state.video.available !== false;
  const emptyTitle = $('empty').querySelector('strong');
  const emptyText = $('empty').querySelector('span:last-child');
  $('empty').hidden = available;
  if (available) {
    emptyTitle.textContent = 'Здесь появится видео';
    emptyText.textContent = 'Выберите запись в панели слева, чтобы начать';
    $('player').poster = `/api/videos/${id}/media?kind=frame&time_s=0`;
    $('player').src = `/api/videos/${id}/media?kind=file`;
  } else {
    emptyTitle.textContent = 'Исходный файл недоступен';
    emptyText.textContent = 'Сохранённые результаты можно просмотреть, но для нового анализа загрузите видео снова';
    $('player').pause();
    $('player').removeAttribute('poster');
    $('player').removeAttribute('src');
    $('player').load();
  }
  $('scrub').max = state.video.duration || 0;
  $('scrub').value = 0;
  $('timeLabel').textContent = '0:00';
  $('analyze').disabled = !available;
  $('playPause').disabled = !available;
  await loadVideos(); await loadScenes(); await loadRuns();
  if (state.runs.length && state.mode === 'automatic' && state.view === 'setup') await selectRun(state.runs[0].id);
  else {$('report').hidden = true; renderRunStatus(); draw()}
}
async function loadScenes() {
  if (!state.video) return;
  $('scenes').setAttribute('aria-busy', 'true');
  state.scenes = (await api(`/api/scenes?video_id=${state.video.id}`)).filter(scene => scene.geometry.mode !== 'automatic');
  $('scenes').innerHTML = state.scenes.map(scene => `<button type="button" data-id="${scene.id}" class="${state.scene?.id === scene.id ? 'active' : ''}" aria-pressed="${state.scene?.id === scene.id}"><strong>${esc(scene.name)}</strong><small>Пользовательская зона</small></button>`).join('') || '<p class="list-empty">Можно обойтись без разметки</p>';
  $('scenes').querySelectorAll('button').forEach(button => button.onclick = () => guard(() => selectScene(button.dataset.id)));
  $('sceneSelect').innerHTML = '<option value="">Новая зона</option>' + state.scenes.map(scene => `<option value="${scene.id}">${esc(scene.name)}</option>`).join('');
  $('sceneSelect').value = state.scene?.id || '';
  $('scenes').removeAttribute('aria-busy');
}
async function selectScene(id) {
  state.scene = state.scenes.find(scene => scene.id === id) || null;
  state.geometry = state.scene ? structuredClone(state.scene.geometry) : blankGeometry();
  state.pending = []; state.dirty = false; state.view = 'setup'; state.detections = []; state.request++;
  $('sceneName').value = state.scene?.name || 'Моя зона';
  renderMode('manual'); await loadScenes(); geometryList(); draw();
}
function renderMode(mode) {
  state.mode = mode;
  $('manualConfig').hidden = mode !== 'manual';
  $('autoDescription').hidden = mode !== 'automatic';
  for (const [id, active] of [['autoMode', mode === 'automatic'], ['manualMode', mode === 'manual']]) {
    $(id).classList.toggle('selected', active);
    $(id).setAttribute('aria-pressed', String(active));
  }
  $('overlay').classList.toggle('editing', mode === 'manual' && state.view === 'setup');
  $('overlayHint').textContent = state.view === 'analysis'
    ? ['queued', 'running'].includes(state.run?.status) ? 'Рамки появятся после завершения обработки.'
      : 'Рамки соответствуют обнаружениям выбранного анализа; линии — сохранённой для него зоне.'
    : mode === 'manual' ? 'Нажимайте на видео, чтобы поставить точки, или введите координаты ниже.'
      : 'После анализа здесь появятся рамки обнаруженных объектов.';
}
function setMode(mode) {
  state.view = 'setup'; state.detections = []; state.request++;
  renderMode(mode); draw();
}
async function loadRuns() {
  if (!state.video) return;
  $('runs').setAttribute('aria-busy', 'true');
  state.runs = await api(`/api/runs?video_id=${state.video.id}`);
  if (state.run) state.run = state.runs.find(run => run.id === state.run.id) || null;
  $('runs').innerHTML = state.runs.map(run => `<button type="button" data-id="${run.id}" class="${state.run?.id === run.id ? 'active' : ''}" aria-pressed="${state.run?.id === run.id}"><strong>${esc(runLabels[run.status] || run.status)} · ${Math.round((run.progress || 0) * 100)}%</strong><small>${new Date(run.created_at).toLocaleString('ru-RU')} ${run.message ? '· ' + esc(run.message) : ''}</small></button>`).join('') || '<p class="list-empty">Первый анализ появится здесь</p>';
  $('runs').querySelectorAll('button').forEach(button => button.onclick = () => guard(() => selectRun(button.dataset.id)));
  $('runs').removeAttribute('aria-busy');
  renderRunStatus();
  renderMode(state.mode);
}
function renderRunStatus() {
  const run = state.run;
  $('runStatus').dataset.status = run?.status || 'idle';
  if (!run) $('runStatus').textContent = state.video ? 'Готово к запуску. Разметка для автоматического анализа не нужна.' : 'Выберите запись и запустите анализ.';
  else {
    const progress = Math.max(0, Math.min(100, Math.round((run.progress || 0) * 100)));
    const elapsed = run.started_at ? (Date.now() - Date.parse(run.started_at)) / 1000 : 0;
    const eta = run.status === 'running' && Number.isFinite(run.eta_s)
      ? `<small>Ориентировочно осталось ${Math.max(1, Math.ceil(run.eta_s / 60))} мин. ${elapsed + run.eta_s > (state.video?.duration || 900) * 2 ? 'Текущий режим может не уложиться в целевое время: остановите анализ и выберите «Быстрый».' : ''}</small>` : '';
    $('runStatus').innerHTML = `<div class="run-status-line"><strong>${esc(runLabels[run.status] || run.status)}</strong><span>${progress}%</span></div><div class="progress-track" role="progressbar" aria-label="Прогресс анализа" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${progress}"><div style="width:${progress}%"></div></div>${eta}${run.message ? `<small>${esc(run.message)}</small>` : ''}`;
  }
  $('cancelRun').hidden = !run || !['queued', 'running', 'stalled'].includes(run.status);
}
async function selectRun(id) {
  state.run = state.runs.find(run => run.id === id);
  if (!state.run) return;
  state.view = 'analysis'; state.detections = []; state.request++;
  const geometry = JSON.parse(state.run.geometry);
  $('cartogramTopology').value = geometry.topology || 'auto';
  if (geometry.mode !== 'automatic') {
    state.scene = state.scenes.find(scene => scene.id === state.run.scene_id) || null;
    if (state.scene) {state.geometry = structuredClone(state.scene.geometry); $('sceneName').value = state.scene.name}
  }
  renderMode(geometry.mode === 'automatic' ? 'automatic' : 'manual');
  await loadScenes(); await loadRuns(); await refreshReport();
  await loadDetections(true);
}
async function refreshReport() {
  if (!state.run) return;
  const runId = state.run.id;
  const interval = Math.max(1, Math.min(1440, Number($('interval').value) || 15)) * 60;
  const result = await api(`/api/runs/${runId}/results?interval=${interval}`);
  const {summary, events, cartogram} = result;
  if (state.run?.id !== runId) return;
  state.events = events;
  if (['queued', 'running'].includes(state.run.status) && !events.length) {
    $('report').hidden = true;
    return;
  }
  $('report').hidden = false;
  const transport = summary.events.filter(event => event.category !== 'pedestrian').length;
  const pedestrians = summary.events.filter(event => event.category === 'pedestrian').length;
  const pending = summary.statuses.review || 0;
  $('summary').innerHTML = [[summary.total, 'Всего учтено'], [transport, 'Транспорт'], [pedestrians, 'Пешеходы'],
    ...(pending ? [[pending, 'На проверке']] : [])].map(([number, text]) => `<div class="metric"><strong>${number}</strong><span>${text}</span></div>`).join('');
  $('reportNote').textContent = pending ? `${pending} событий ожидают проверки и не включены в итог`
    : ['queued', 'running'].includes(state.run.status) ? 'Предварительные результаты — анализ ещё не завершён'
      : 'Данные сохранены для этого анализа';

  const counts = new Map();
  summary.events.forEach(event => counts.set(event.category, (counts.get(event.category) || 0) + 1));
  $('categoryChart').innerHTML = barList([...counts].sort((a, b) => b[1] - a[1]).map(([category, count]) => ({label: labels[category] || category, count, category})));
  const intervals = new Map();
  summary.intervals.forEach(item => intervals.set(item.start_s, (intervals.get(item.start_s) || 0) + item.count));
  $('intervalChart').innerHTML = barList([...intervals].sort((a, b) => a[0] - b[0]).map(([start, count]) => ({label: `${formatTime(start)}–${formatTime(start + interval)}`, count, category: 'time'})));
  renderCartogram(cartogram);

  const manual = summary.geometry.mode !== 'automatic';
  $('routes').hidden = !manual;
  if (manual) $('routeRows').innerHTML = `<table><thead><tr><th>Откуда</th><th>Куда</th><th>Категория</th><th>Количество</th></tr></thead><tbody>${summary.matrix.map(row => `<tr><td>${esc(row.from)}</td><td>${esc(row.to)}</td><td>${esc(labels[row.category] || row.category)}</td><td>${row.count}</td></tr>`).join('') || '<tr><td colspan="4">Нет учтённых проездов</td></tr>'}</tbody></table>`;
  $('events').innerHTML = events.map(event => `<tr><td>${formatTime(event.time_s)} <small>(${event.time_s.toFixed(2)} с)</small></td><td>${esc(labels[event.category] || event.category)}</td><td>${esc(event.from_direction)}</td><td>${esc(event.to_direction)}</td><td><span class="status ${esc(event.status)}">${esc(labels[event.status] || event.status)}</span></td><td><button type="button" data-id="${event.id}">Править</button></td></tr>`).join('') || '<tr><td colspan="6" class="muted">Событий пока нет</td></tr>';
  $('events').querySelectorAll('button').forEach(button => button.onclick = () => openEvent(state.events.find(event => event.id === button.dataset.id)));
  for (const ext of ['xlsx', 'csv', 'json']) $(ext).href = `/api/runs/${runId}/export/${ext}?interval=${interval}`;
}
function barList(data) {
  if (!data.length) return '<p class="list-empty">Данные появятся после обнаружения объектов.</p>';
  const max = Math.max(...data.map(item => item.count), 1);
  return data.map(item => `<div class="bar-row"><div class="bar-label"><span>${esc(item.label)}</span><strong>${item.count}</strong></div><div class="bar-track"><div class="bar-fill ${esc(item.category)}" style="width:${item.count / max * 100}%"></div></div></div>`).join('');
}
function renderCartogram(data) {
  const three = data.topology === 'three_way';
  const armLabel = {'Север': 'Сверху', 'Восток': 'Справа', 'Юг': 'Снизу',
    'Запад': 'Слева', 'Юго-восток': 'Правый луч', 'Юго-запад': 'Левый луч'};
  const positions = three ? {'Север': [180, 25], 'Юго-восток': [325, 280], 'Юго-запад': [35, 280]}
    : {'Север': [180, 25], 'Восток': [335, 165], 'Юг': [180, 305], 'Запад': [25, 165]};
  if (data.topology === 'unknown') {
    $('cartogram').innerHTML = '';
    $('cartogramTable').innerHTML = '';
    $('cartogramNote').textContent = 'Тип перекрёстка не удалось определить по траекториям. Выберите трёхлучевую или пересекающуюся схему: пересчитывать видео не потребуется.';
    return;
  }
  $('cartogramNote').textContent = `${data.source === 'reference' ? 'Вид узла взят из схемы приложенного примера. ' : ''}Направление определено для ${data.routed} из ${data.total} учтённых объектов${data.motion_estimated ? ` (из них ${data.motion_estimated} — оценка по движению в кадре)` : ''}${data.user_directions ? `; ${data.user_directions} — по вашим именованным линиям` : ''}. ${data.unresolved ? `Для ${data.unresolved} направление не определено и на схеме не показано. ` : ''}Без пользовательских линий лучи условные, не географические направления дорог. Толщина и число на стрелке — поток, цвет — преобладающая категория; остальные категории перечислены в таблице.`;
  const colors = {pedestrian: '#d97706', car: '#2563eb', truck: '#475569', bus: '#7c3aed', motorcycle: '#0e7490', bicycle: '#0f766e'};
  const arms = data.arms.map(name => positions[name]).filter(Boolean);
  const roads = arms.map(([x, y]) => `<line x1="180" y1="165" x2="${x}" y2="${y}" stroke="#dbe5f0" stroke-width="62" stroke-linecap="round"/><line x1="180" y1="165" x2="${x}" y2="${y}" stroke="#fff" stroke-width="2" stroke-dasharray="9 11"/>`).join('');
  const markers = Object.entries({...colors, other: '#64748b'}).map(([kind, color]) => `<marker id="tip-${kind}" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="${color}"/></marker>`).join('');
  const flowsByRoute = new Map();
  for (const row of data.matrix) {
    const key = `${row.from}\u0000${row.to}`;
    if (!flowsByRoute.has(key)) flowsByRoute.set(key, {from: row.from, to: row.to, count: 0, categories: []});
    const flow = flowsByRoute.get(key);
    flow.count += row.count;
    flow.categories.push(row);
  }
  const flows = [...flowsByRoute.values()].sort((a, b) => b.count - a.count);
  const flowLabels = [];
  const paths = flows.map((flow, index) => {
    const start = positions[flow.from], end = positions[flow.to];
    if (!start || !end) return '';
    const a = [180 + (start[0] - 180) * .72, 165 + (start[1] - 165) * .72];
    const b = [180 + (end[0] - 180) * .72, 165 + (end[1] - 165) * .72];
    const opposite = flows.some(other => other.from === flow.to && other.to === flow.from);
    const side = flow.from < flow.to ? 1 : -1;
    const offset = opposite ? side * 24 : ((index % 3) - 1) * 7;
    const control = [180 + offset, 165 + offset];
    const dominant = flow.categories.sort((first, second) => second.count - first.count)[0].category;
    const color = colors[dominant] || '#64748b';
    const width = Math.min(13, 2.5 + Math.log2(flow.count + 1) * 2);
    const title = flow.categories.map(item => `${labels[item.category] || item.category}: ${item.count}`).join('; ');
    const labelX = (a[0] + 2 * control[0] + b[0]) / 4;
    const labelY = (a[1] + 2 * control[1] + b[1]) / 4 - 7;
    if (index < 8) flowLabels.push(`<text x="${labelX}" y="${labelY}" text-anchor="middle" font-size="13" font-weight="800" fill="#10243f" stroke="#f8fafc" stroke-width="5" paint-order="stroke">${flow.count}</text>`);
    return `<path d="M${a[0]},${a[1]} Q${control[0]},${control[1]} ${b[0]},${b[1]}" fill="none" stroke="${color}" stroke-width="${width}" stroke-opacity=".85" marker-end="url(#tip-${colors[dominant] ? dominant : 'other'})"><title>${esc(armLabel[flow.from] || flow.from)} → ${esc(armLabel[flow.to] || flow.to)}: ${esc(title)}</title></path>`;
  }).join('');
  const names = data.arms.map(name => {
    const [x, y] = positions[name];
    const labelX = x < 50 ? 49 : x > 310 ? 311 : x;
    return `<text x="${labelX}" y="${y < 50 ? 16 : y > 270 ? 325 : y + 5}" text-anchor="middle" fill="#10243f" font-size="12" font-weight="700">${esc(armLabel[name] || name)}</text>`;
  }).join('');
  $('cartogram').innerHTML = `<svg viewBox="0 0 360 335" role="img" aria-label="${three ? 'Трёхлучевой' : 'Пересекающийся'} узел: ${data.routed} оценочных маршрутов"><defs>${markers}</defs>${roads}${three ? '<path d="M180 137 L150 185 L210 185 Z" fill="#bfdbfe"/>' : ''}${paths}${flowLabels.join('')}${names}</svg>`;
  $('cartogramTable').innerHTML = `<table><thead><tr><th>Откуда (условно)</th><th>Куда (условно)</th><th>Категория</th><th>Количество</th></tr></thead><tbody>${data.matrix.map(row => `<tr><td>${esc(armLabel[row.from] || row.from)}</td><td>${esc(armLabel[row.to] || row.to)}</td><td>${esc(labels[row.category] || row.category)}</td><td>${row.count}</td></tr>`).join('') || '<tr><td colspan="4">Маршрутов с определённым направлением пока нет</td></tr>'}</tbody></table>`;
}

function geometryList() {
  const geometry = state.geometry;
  const parts = [...geometry.entries.map((item, index) => ['entries', index, `Въезд: ${item.name}`]),
    ...geometry.exits.map((item, index) => ['exits', index, `Выезд: ${item.name}`])];
  if (geometry.roi?.length) parts.push(['roi', 0, `Область (${geometry.roi.length} точек)`]);
  $('geometryList').innerHTML = parts.map(([kind, index, text]) => `<span class="chip">${esc(text)} <button type="button" data-kind="${kind}" data-i="${index}" aria-label="Удалить ${esc(text)}">×</button></span>`).join('') || '<span class="list-empty">Линии ещё не заданы</span>';
  $('geometryList').querySelectorAll('button').forEach(button => button.onclick = () => {
    if (button.dataset.kind === 'roi') geometry.roi = [];
    else geometry[button.dataset.kind].splice(Number(button.dataset.i), 1);
    state.dirty = true; geometryList(); draw();
  });
}
function addPoint(point) {
  if (!state.video || state.mode !== 'manual') return;
  state.view = 'setup'; state.detections = []; state.request++;
  renderMode('manual');
  state.pending.push(point);
  if (state.tool !== 'roi' && state.pending.length === 2) {
    const name = $('lineName').value.trim();
    const kind = state.tool === 'entry' ? 'entries' : 'exits';
    if (!name || state.geometry[kind].some(item => item.name === name)) {
      flash(!name ? 'Введите название линии' : 'Название линии уже используется в этом направлении');
      state.pending = []; draw(); return;
    }
    state.geometry[kind].push({name, points: state.pending});
    state.pending = []; state.dirty = true; geometryList();
  }
  draw();
}
function setTool(tool) {
  state.tool = tool; state.pending = [];
  document.querySelectorAll('[data-tool]').forEach(button => {
    const selected = button.dataset.tool === tool;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  draw();
}
function draw() {
  const canvas = $('overlay');
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(rect.width * ratio);
  canvas.height = Math.round(rect.height * ratio);
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  const width = rect.width, height = rect.height;
  const geometry = state.view === 'analysis' && state.run ? JSON.parse(state.run.geometry) : state.mode === 'manual' ? state.geometry : null;
  function line(points, color, fill = false) {
    if (!points?.length) return;
    ctx.beginPath();
    points.forEach(([x, y], index) => index ? ctx.lineTo(x * width, y * height) : ctx.moveTo(x * width, y * height));
    if (fill && points.length >= 3) {ctx.closePath(); ctx.fillStyle = '#38bdf833'; ctx.fill()}
    ctx.lineWidth = 3; ctx.strokeStyle = color; ctx.stroke();
    for (const [x, y] of points) {ctx.beginPath(); ctx.arc(x * width, y * height, 5, 0, 2 * Math.PI); ctx.fillStyle = color; ctx.fill()}
  }
  if (geometry) {
    line(geometry.roi, '#38bdf8', true);
    for (const item of geometry.entries || []) line(item.points, '#fbbf24');
    for (const item of geometry.exits || []) line(item.points, '#22d3ee');
  }
  if (state.view === 'setup' && state.mode === 'manual') line(state.pending, '#fb7185');
  if (state.view !== 'analysis') return;
  for (const object of state.detections) {
    const [x1, y1, x2, y2] = object.box;
    const x = x1 * width, y = y1 * height, w = (x2 - x1) * width, h = (y2 - y1) * height;
    const recorded = state.events.find(event => event.tracker_id === object.id && event.status !== 'discarded');
    const category = recorded?.category || object.category;
    const color = category === 'pedestrian' ? '#fbbf24' : category === 'car' ? '#60a5fa' : '#22d3ee';
    ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.strokeRect(x, y, w, h);
    const text = `${labels[category] || category} · #${object.id}`;
    ctx.font = '600 12px system-ui, sans-serif';
    const tagWidth = Math.min(ctx.measureText(text).width + 14, width);
    const tagX = Math.max(0, Math.min(x, width - tagWidth));
    const tagY = y > 24 ? y - 23 : y;
    ctx.fillStyle = '#061a31eb'; ctx.fillRect(tagX, tagY, tagWidth, 21);
    ctx.fillStyle = color; ctx.fillText(text, tagX + 7, tagY + 15, tagWidth - 12);
  }
}
async function loadDetections(force = false) {
  if (state.view !== 'analysis' || !state.run || !state.video) return;
  if (!force && performance.now() - state.lastDetection < 250) return;
  state.lastDetection = performance.now();
  const request = ++state.request, runId = state.run.id;
  try {
    const frame = await api(`/api/runs/${runId}/results?view=detections&time_s=${Math.max(0, $('player').currentTime || 0)}`);
    if (request !== state.request || state.run?.id !== runId || state.view !== 'analysis') return;
    state.detections = frame.objects; draw();
  } catch (error) {if (request === state.request) {state.detections = []; draw()}}
}
function openEvent(event) {
  if (!state.run) return;
  const geometry = JSON.parse(state.run.geometry);
  const auto = geometry.mode === 'automatic';
  $('eventFrom').innerHTML = auto ? '<option>В кадре</option>' : geometry.entries.map(item => `<option>${esc(item.name)}</option>`).join('');
  $('eventTo').innerHTML = auto ? '<option>В кадре</option>' : geometry.exits.map(item => `<option>${esc(item.name)}</option>`).join('');
  $('dialogTitle').textContent = event ? 'Правка события' : 'Добавить пропущенный объект';
  $('eventId').value = event?.id || '';
  $('eventVersion').value = event?.version || '';
  $('eventTime').value = event?.time_s ?? $('player').currentTime.toFixed(2);
  $('eventCategory').value = event?.category || 'car';
  $('eventFrom').value = event?.from_direction || (auto ? 'В кадре' : geometry.entries[0]?.name);
  $('eventTo').value = event?.to_direction || (auto ? 'В кадре' : geometry.exits[0]?.name);
  $('eventStatus').value = event?.status || 'confirmed';
  $('eventReason').value = '';
  $('eventDialog').showModal();
}

$('upload').onchange = event => guard(async () => {
  const file = event.target.files?.[0]; if (!file) return;
  const uploadLabel = event.target.closest('.upload');
  $('uploadStatus').textContent = 'Загрузка видео…';
  uploadLabel?.classList.add('is-loading');
  uploadLabel?.setAttribute('aria-busy', 'true');
  event.target.disabled = true;
  const form = new FormData(); form.append('file', file);
  try {
    const result = await api('/api/videos', {method: 'POST', body: form});
    await loadVideos(); await selectVideo(result.id);
    $('uploadStatus').textContent = 'Видео загружено · ' + result.name;
    flash('Видео загружено. Теперь можно запустить анализ без разметки.', true);
  } catch (error) {$('uploadStatus').textContent = 'Не удалось загрузить видео'; throw error}
  finally {
    event.target.value = '';
    event.target.disabled = false;
    uploadLabel?.classList.remove('is-loading');
    uploadLabel?.removeAttribute('aria-busy');
  }
});
$('autoMode').onclick = () => setMode('automatic');
$('manualMode').onclick = () => setMode('manual');
$('profile').onchange = event => {
  $('sampleFpsControl').hidden = event.target.value !== 'fast';
  $('autoDescription').textContent = event.target.value === 'fast'
    ? 'Быстрый режим: одна YOLO11s обрабатывает выбранную частоту кадров (по умолчанию 6 кадров/с), ByteTrack связывает объекты между кадрами. Учитываются пешеходы, велосипеды, легковые автомобили, мотоциклы, автобусы и грузовики. При понижении частоты можно пропустить быстрые объекты.'
    : 'Ансамбль: YOLO11m и YOLOv10m с объединением рамок и ByteTrack обрабатывают каждый кадр. Этот режим значительно медленнее быстрого.';
};
$('overlay').onclick = event => {
  if (state.view !== 'setup' || state.mode !== 'manual' || !state.video) return;
  const rect = $('overlay').getBoundingClientRect();
  addPoint([(event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height]
    .map(value => Math.max(0, Math.min(1, value))));
};
$('addPoint').onclick = () => {
  const x = $('pointX').valueAsNumber, y = $('pointY').valueAsNumber;
  if (![x, y].every(value => Number.isFinite(value) && value >= 0 && value <= 100)) return flash('Координаты должны быть от 0 до 100%');
  addPoint([x / 100, y / 100]);
};
document.querySelectorAll('[data-tool]').forEach(button => button.onclick = () => setTool(button.dataset.tool));
$('finishRoi').onclick = () => {
  if (state.pending.length < 3) return flash('Отметьте минимум три точки области');
  state.geometry.roi = state.pending; state.pending = []; state.dirty = true; geometryList(); draw();
};
$('undo').onclick = () => {state.pending.pop(); draw()};
$('sceneSelect').onchange = event => guard(() => selectScene(event.target.value));
$('sceneName').oninput = () => {state.dirty = true};
$('saveScene').onclick = () => guard(async () => {
  const button = $('saveScene');
  setBusy(button, true, 'Сохраняем');
  try {
    if (!state.video) throw Error('Сначала выберите видео');
    const name = $('sceneName').value.trim();
    if (!name) throw Error('Введите название зоны');
    const payload = {video_id: state.video.id, name, geometry: {...state.geometry, mode: 'manual'}};
    const path = state.scene ? `/api/scenes/${state.scene.id}` : '/api/scenes';
    const scene = await api(path, {method: state.scene ? 'PUT' : 'POST',
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    await loadScenes(); await selectScene(scene.id); flash('Зона сохранена. Можно запустить анализ.', true);
  } finally {setBusy(button, false)}
});
$('analyze').onclick = () => guard(async () => {
  if (!state.video) throw Error('Сначала загрузите видео');
  if (state.mode === 'manual' && (!state.scene || state.dirty)) throw Error('Сохраните пользовательскую зону перед запуском');
  const payload = state.mode === 'automatic' ? {video_id: state.video.id} : {scene_id: state.scene.id};
  payload.profile = $('profile').value;
  if (payload.profile === 'fast') {
    const sampleFps = $('sampleFps').valueAsNumber;
    if (!Number.isFinite(sampleFps) || sampleFps < 2 || sampleFps > 12) throw Error('Частота быстрого режима должна быть от 2 до 12 кадров/с');
    payload.sample_fps = sampleFps;
  }
  payload.topology = $('topology').value;
  setBusy($('analyze'), true, 'Запускаем');
  try {
    const run = await api('/api/runs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    await loadRuns(); await selectRun(run.id);
    flash('Анализ поставлен в очередь. Статус обновится автоматически.', true);
  } finally {
    setBusy($('analyze'), false);
    $('analyze').disabled = !state.video;
  }
});
$('cancelRun').onclick = () => guard(async () => {
  if (!state.run) return;
  setBusy($('cancelRun'), true, 'Останавливаем');
  try {
    await api(`/api/runs/${state.run.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action: 'cancel'})});
    await loadRuns(); flash('Остановка анализа запрошена', true);
  } finally {setBusy($('cancelRun'), false)}
});
$('refresh').onclick = () => guard(async () => {
  setBusy($('refresh'), true, 'Обновляем');
  try {await loadRuns(); await refreshReport(); await loadDetections(true)}
  finally {setBusy($('refresh'), false)}
});
$('interval').onchange = () => guard(refreshReport);
$('cartogramTopology').onchange = event => guard(async () => {
  if (!state.run) return;
  await api(`/api/runs/${state.run.id}`, {method: 'PATCH',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'set_topology', topology: event.target.value})});
  await loadRuns(); await refreshReport();
});
$('scrub').oninput = event => {$('player').currentTime = Number(event.target.value); loadDetections(true)};
$('player').ontimeupdate = () => {
  $('scrub').value = $('player').currentTime;
  $('timeLabel').textContent = formatTime($('player').currentTime);
  loadDetections();
};
$('player').onseeked = () => loadDetections(true);
$('player').onloadedmetadata = () => {
  if (Number.isFinite($('player').duration)) $('scrub').max = $('player').duration;
  draw();
};
$('player').onplay = () => {
  $('playPause').textContent = 'Пауза';
  $('playPause').setAttribute('aria-label', 'Приостановить видео');
};
$('player').onpause = () => {
  $('playPause').textContent = 'Воспроизвести';
  $('playPause').setAttribute('aria-label', 'Воспроизвести видео');
};
$('player').onerror = () => {
  if ($('player').getAttribute('src')) flash('Не удалось воспроизвести видео. Проверьте формат файла.');
};
$('playPause').onclick = () => {
  if (!state.video) return;
  if ($('player').paused) guard(() => $('player').play()); else $('player').pause();
};
window.addEventListener('resize', draw);
$('manual').onclick = () => {if (state.run) openEvent(null)};
$('eventForm').onsubmit = event => {
  event.preventDefault();
  if (event.submitter?.value === 'cancel') {$('eventDialog').close(); return}
  guard(async () => {
    setBusy($('eventSave'), true, 'Сохраняем');
    try {
      const id = $('eventId').value;
      const payload = {category: $('eventCategory').value, from_direction: $('eventFrom').value,
        to_direction: $('eventTo').value, time_s: Number($('eventTime').value),
        status: $('eventStatus').value, reason: $('eventReason').value};
      if (id) {payload.id = id; payload.version = Number($('eventVersion').value)}
      await api(`/api/runs/${state.run.id}/events`, {
        method: id ? 'PATCH' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
      $('eventDialog').close(); await refreshReport(); flash('Событие сохранено', true);
    } finally {setBusy($('eventSave'), false)}
  });
};
setInterval(() => {
  if (state.run && ['queued', 'running', 'stalled'].includes(state.run.status)) guard(async () => {
    await loadRuns(); await refreshReport();
    if (state.run?.status === 'completed') await loadDetections(true);
  });
}, 3000);
geometryList(); setTool('entry'); document.documentElement.dataset.ready = 'true'; guard(loadVideos);
