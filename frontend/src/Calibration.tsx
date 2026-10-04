import { useState, useRef } from "react";
import { Plus, Trash2, Undo2, Save, MousePointer2 } from "lucide-react";
import { api, url } from "./api";
import type { Project, Calibration as Config, Point } from "./types";

import TopologyEditor from "./TopologyEditor";

type Draft = { kind: "entry" | "exit" | "line"; points: Point[] };
export default function Calibration({
  project,
  onSaved,
  onError,
}: {
  project: Project;
  onSaved: () => void;
  onError: (s: string) => void;
}) {
  const [config, setConfig] = useState<Config>(structuredClone(project.config));
  const [draft, setDraft] = useState<Draft | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const svg = useRef<SVGSVGElement>(null);
  const drag = useRef<{ id: string; index: number } | null>(null);
  const all = [...config.zones, ...config.lines];
  const current = all.find((s) => s.id === selected);
  function point(e: React.PointerEvent): Point {
    const r = svg.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
      y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
    };
  }
  function finish(d = draft) {
    if (!d || d.points.length < (d.kind === "line" ? 2 : 3)) return;
    const id = crypto.randomUUID();
    const name =
      d.kind === "entry"
        ? `Въезд ${config.zones.filter((z) => z.kind === "entry").length + 1}`
        : d.kind === "exit"
          ? `Выезд ${config.zones.filter((z) => z.kind === "exit").length + 1}`
          : `Линия ${config.lines.length + 1}`;
    setConfig((c) =>
      d.kind === "line"
        ? { ...c, lines: [...c.lines, { id, name, points: d.points }] }
        : {
            ...c,
            zones: [...c.zones, { id, name, kind: d.kind, points: d.points }],
          },
    );
    setSelected(id);
    setDraft(null);
  }
  function updatePoint(id: string, index: number, p: Point) {
    setConfig((c) => ({
      ...c,
      zones: c.zones.map((s) =>
        s.id === id
          ? { ...s, points: s.points.map((v, i) => (i === index ? p : v)) }
          : s,
      ),
      lines: c.lines.map((s) =>
        s.id === id
          ? { ...s, points: s.points.map((v, i) => (i === index ? p : v)) }
          : s,
      ),
    }));
  }
  function rename(id: string, name: string) {
    setConfig((c) => ({
      ...c,
      zones: c.zones.map((s) => (s.id === id ? { ...s, name } : s)),
      lines: c.lines.map((s) => (s.id === id ? { ...s, name } : s)),
    }));
  }
  async function save(recalculate: boolean) {
    setBusy(true);
    try {
      await api(`/projects/${project.id}/calibration`, {
        method: "PUT",
        body: JSON.stringify(config),
      });
      if (recalculate)
        await api(`/projects/${project.id}/analysis`, {
          method: "POST",
          body: JSON.stringify({ recalculate: true }),
        });
      onSaved();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <TopologyEditor
        project={project}
        value={config.intersection}
        onChange={(intersection) => setConfig((c) => ({ ...c, intersection }))}
        onSave={() => save(!!project.result_run)}
        busy={busy}
      />
      <div className="calibration-layout">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Настройка направлений</h2>
              <p>
                Автоматический режим работает без зон. Добавьте их, если потоки
                требуют уточнения.
              </p>
            </div>
          </div>
          <div className="toolbar">
            <button onClick={() => setDraft({ kind: "entry", points: [] })}>
              <Plus size={16} /> Зона въезда
            </button>
            <button onClick={() => setDraft({ kind: "exit", points: [] })}>
              <Plus size={16} /> Зона выезда
            </button>
            <button onClick={() => setDraft({ kind: "line", points: [] })}>
              <Plus size={16} /> Линия
            </button>
          </div>
          <div
            className="frame-editor"
            style={{
              aspectRatio: `${project.video.width}/${project.video.height}`,
            }}
          >
            <img
              src={url(`/projects/${project.id}/media/preview`)}
              alt="Первый кадр видео для настройки направлений"
            />
            <svg
              ref={svg}
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
              onPointerDown={(e) => {
                if (draft) {
                  const d = { ...draft, points: [...draft.points, point(e)] };
                  setDraft(d);
                  if (d.kind === "line" && d.points.length === 2) finish(d);
                }
              }}
              onPointerMove={(e) => {
                if (drag.current)
                  updatePoint(drag.current.id, drag.current.index, point(e));
              }}
              onPointerUp={() => {
                drag.current = null;
              }}
              onPointerCancel={() => {
                drag.current = null;
              }}
            >
              {all.map((s) => (
                <g key={s.id}>
                  <polygon
                    points={s.points
                      .map((p) => `${p.x * 1000},${p.y * 1000}`)
                      .join(" ")}
                    fill={"kind" in s ? "rgba(255,255,255,.15)" : "none"}
                    stroke={
                      "kind" in s && s.kind === "entry" ? "#62e8b4" : "#ffcf75"
                    }
                    strokeWidth={selected === s.id ? 5 : 3}
                    vectorEffect="non-scaling-stroke"
                    onClick={() => !draft && setSelected(s.id)}
                  />
                  <text
                    x={s.points[0].x * 1000}
                    y={s.points[0].y * 1000 - 14}
                    fill="white"
                    stroke="#17202a"
                    strokeWidth={3}
                    paintOrder="stroke"
                    fontSize={26}
                  >
                    {s.name}
                  </text>
                  {s.points.map((p, i) => (
                    <circle
                      key={i}
                      cx={p.x * 1000}
                      cy={p.y * 1000}
                      r={9}
                      fill="white"
                      stroke="#17202a"
                      strokeWidth={2}
                      onPointerDown={(e) => {
                        if (draft) return;
                        e.stopPropagation();
                        setSelected(s.id);
                        drag.current = { id: s.id, index: i };
                        e.currentTarget.setPointerCapture(e.pointerId);
                      }}
                    />
                  ))}
                </g>
              ))}
              {draft && (
                <polyline
                  points={draft.points
                    .map((p) => `${p.x * 1000},${p.y * 1000}`)
                    .join(" ")}
                  fill="none"
                  stroke="white"
                  strokeWidth={4}
                  strokeDasharray="8 5"
                />
              )}
            </svg>
          </div>
          {draft ? (
            <div className="toolbar">
              <span>Нажимайте на кадр: {draft.points.length} точек</span>
              <button
                onClick={() =>
                  setDraft({ ...draft, points: draft.points.slice(0, -1) })
                }
              >
                <Undo2 size={16} /> Отменить точку
              </button>
              <button onClick={() => setDraft(null)}>Отмена</button>
              <button
                className="primary"
                disabled={draft.points.length < 3}
                onClick={() => finish()}
              >
                Завершить зону
              </button>
            </div>
          ) : (
            <p className="hint">
              <MousePointer2 size={15} /> Перетаскивайте вершины или задайте
              координаты справа. Для линии A → B означает переход на
              положительную сторону от её первой точки ко второй.
            </p>
          )}
          <div className="toolbar bottom">
            <button disabled={busy || !!draft} onClick={() => save(false)}>
              <Save size={16} /> Сохранить
            </button>
            {project.result_run && (
              <button
                className="primary"
                disabled={busy || !!draft}
                onClick={() => save(true)}
              >
                Сохранить и пересчитать
              </button>
            )}
          </div>
        </section>
        <aside className="panel shape-list">
          <h3>
            Зоны и линии <span className="muted">{all.length}</span>
          </h3>
          {!all.length && (
            <p className="muted">
              Без фигур система определяет направления по похожим траекториям.
            </p>
          )}
          {all.map((s) => (
            <div
              className={"shape-row " + (selected === s.id ? "selected" : "")}
              key={s.id}
            >
              <button
                className="shape-select"
                onClick={() => setSelected(s.id)}
              >
                {"kind" in s
                  ? s.kind === "entry"
                    ? "Въезд"
                    : "Выезд"
                  : "Линия"}
              </button>
              <input
                aria-label="Название фигуры"
                value={s.name}
                maxLength={120}
                onFocus={() => setSelected(s.id)}
                onChange={(e) => rename(s.id, e.target.value)}
              />
              <button
                className="icon-button"
                aria-label={`Удалить ${s.name}`}
                onClick={() =>
                  setConfig((c) => ({
                    ...c,
                    zones: c.zones.filter((z) => z.id !== s.id),
                    lines: c.lines.filter((z) => z.id !== s.id),
                  }))
                }
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
          {current && (
            <div className="coordinates">
              <h4>Вершины: доля ширины / высоты</h4>
              {current.points.map((p, i) => (
                <div key={i}>
                  <span>{i + 1}</span>
                  {(["x", "y"] as const).map((axis) => (
                    <label key={axis}>
                      {axis.toUpperCase()}
                      <input
                        type="number"
                        min={0}
                        max={1}
                        step={0.01}
                        value={Number(p[axis].toFixed(3))}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          if (v >= 0 && v <= 1)
                            updatePoint(current.id, i, { ...p, [axis]: v });
                        }}
                      />
                    </label>
                  ))}
                </div>
              ))}
            </div>
          )}
          <p className="hint">
            Для движения между зонами нужны въезд и последующий выезд. Линии
            считаются отдельно; повторные пересечения одним треком не
            увеличивают результат.
          </p>
        </aside>
      </div>
    </>
  );
}
