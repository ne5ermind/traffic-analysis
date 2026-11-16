import {labels} from '../constants.js';

const armLabels = {'Север': 'Сверху', 'Восток': 'Справа', 'Юг': 'Снизу', 'Запад': 'Слева', 'Юго-восток': 'Правый луч', 'Юго-запад': 'Левый луч'};
const colors = {pedestrian: '#d97706', car: '#2563eb', truck: '#475569', bus: '#7c3aed', motorcycle: '#0e7490', bicycle: '#0f766e'};

export function Cartogram({data}) {
  if (!data || data.topology === 'unknown') return null;
  const three = data.topology === 'three_way';
  const positions = three ? {'Север': [180, 25], 'Юго-восток': [325, 280], 'Юго-запад': [35, 280]} : {'Север': [180, 25], 'Восток': [335, 165], 'Юг': [180, 305], 'Запад': [25, 165]};
  const grouped = new Map();
  data.matrix.forEach(row => {
    const key = `${row.from}\0${row.to}`;
    const flow = grouped.get(key) || {from: row.from, to: row.to, count: 0, categories: []};
    flow.count += row.count; flow.categories.push(row); grouped.set(key, flow);
  });
  const flows = [...grouped.values()].sort((a, b) => b.count - a.count);
  return <div className="cartogram"><svg viewBox="0 0 360 335" role="img" aria-label={`${three ? 'Трёхлучевой' : 'Пересекающийся'} узел: ${data.routed} оценочных маршрутов`}>
    <defs>{Object.entries({...colors, other: '#64748b'}).map(([kind, color]) => <marker key={kind} id={`tip-${kind}`} markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill={color} /></marker>)}</defs>
    {data.arms.map(name => positions[name]).filter(Boolean).map(([x, y], index) => <g key={index}><line x1="180" y1="165" x2={x} y2={y} stroke="#dbe5f0" strokeWidth="62" strokeLinecap="round"/><line x1="180" y1="165" x2={x} y2={y} stroke="#fff" strokeWidth="2" strokeDasharray="9 11"/></g>)}
    {three && <path d="M180 137 L150 185 L210 185 Z" fill="#bfdbfe" />}
    {flows.map((flow, index) => {
      const start = positions[flow.from], end = positions[flow.to]; if (!start || !end) return null;
      const a = [180 + (start[0] - 180) * .72, 165 + (start[1] - 165) * .72];
      const b = [180 + (end[0] - 180) * .72, 165 + (end[1] - 165) * .72];
      const opposite = flows.some(other => other.from === flow.to && other.to === flow.from);
      const offset = opposite ? (flow.from < flow.to ? 24 : -24) : ((index % 3) - 1) * 7;
      const control = [180 + offset, 165 + offset];
      const dominant = [...flow.categories].sort((first, second) => second.count - first.count)[0].category;
      const kind = colors[dominant] ? dominant : 'other';
      return <g key={`${flow.from}-${flow.to}`}><path d={`M${a[0]},${a[1]} Q${control[0]},${control[1]} ${b[0]},${b[1]}`} fill="none" stroke={colors[dominant] || '#64748b'} strokeWidth={Math.min(13, 2.5 + Math.log2(flow.count + 1) * 2)} strokeOpacity=".85" markerEnd={`url(#tip-${kind})`}><title>{`${armLabels[flow.from] || flow.from} → ${armLabels[flow.to] || flow.to}: ${flow.categories.map(item => `${labels[item.category] || item.category}: ${item.count}`).join('; ')}`}</title></path>{index < 8 && <text x={(a[0] + 2 * control[0] + b[0]) / 4} y={(a[1] + 2 * control[1] + b[1]) / 4 - 7} textAnchor="middle" fontSize="13" fontWeight="800" fill="#10243f" stroke="#f8fafc" strokeWidth="5" paintOrder="stroke">{flow.count}</text>}</g>;
    })}
    {data.arms.map(name => { const [x, y] = positions[name]; return <text key={name} x={x < 50 ? 49 : x > 310 ? 311 : x} y={y < 50 ? 16 : y > 270 ? 325 : y + 5} textAnchor="middle" fill="#10243f" fontSize="12" fontWeight="700">{armLabels[name] || name}</text>; })}
  </svg></div>;
}

export function CartogramTable({rows = []}) {
  return <div className="tablewrap"><table><thead><tr><th>Откуда (условно)</th><th>Куда (условно)</th><th>Категория</th><th>Количество</th></tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={`${row.from}-${row.to}-${row.category}-${index}`}><td>{armLabels[row.from] || row.from}</td><td>{armLabels[row.to] || row.to}</td><td>{labels[row.category] || row.category}</td><td>{row.count}</td></tr>) : <tr><td colSpan="4">Маршрутов с определённым направлением пока нет</td></tr>}</tbody></table></div>;
}
