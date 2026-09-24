import { useState } from "react";
import type { Project, IntersectionConfig, Point } from "./types";
import { url } from "./api";

export default function TopologyEditor({
  project,
  value,
  onChange,
  onSave,
  busy,
}: {
  project: Project;
  value?: IntersectionConfig | null;
  onChange: (value: IntersectionConfig | null) => void;
  onSave: () => void;
  busy: boolean;
}) {
  const [selected, setSelected] = useState("center");
  function begin() {
    const proposed = project.result?.intersection;
    onChange({
      intersection_type: [
        "t",
        "y",
        "four_way",
        "straight",
        "multi_way",
      ].includes(proposed?.intersection_type || "")
        ? proposed!.intersection_type!
        : "t",
      center: proposed?.center || { x: 0.5, y: 0.5 },
      approaches: proposed?.approaches?.length
        ? proposed.approaches.map(({ id, label, x, y }) => ({
            id,
            label,
            x,
            y,
          }))
        : [
            { id: "a", label: "Слева", x: 0.1, y: 0.5 },
            { id: "b", label: "Справа", x: 0.9, y: 0.5 },
            { id: "c", label: "Снизу", x: 0.5, y: 0.9 },
          ],
    });
  }
  function position(id: string, point: Point) {
    if (!value) return;
    onChange(
      id === "center"
        ? { ...value, center: point }
        : {
            ...value,
            approaches: value.approaches.map((a) =>
              a.id === id ? { ...a, ...point } : a,
            ),
          },
    );
  }
  return (
    <section className="panel topology-editor">
      <div className="panel-heading">
        <div>
          <h2>Геометрия перекрёстка</h2>
          <p>
            Если модели ошиблись, укажите центр и по одной точке на каждом
            подходе.
          </p>
        </div>
        <button onClick={() => (value ? onChange(null) : begin())}>
          {value ? "Вернуть автоопределение" : "Уточнить схему"}
        </button>
      </div>
      {value && (
        <>
          <p className="hint">
            Выберите точку в списке и нажмите на кадр. Подход отмечайте вдали от
            центра, там, где машины входят и выходят из видимой области.
            Координаты также можно ввести с клавиатуры.
          </p>
          <div className="topology-layout">
            <div
              className="frame-editor"
              style={{
                aspectRatio: `${project.video.width}/${project.video.height}`,
              }}
            >
              <img
                src={url(`/projects/${project.id}/media/preview`)}
                alt="Кадр с центром перекрёстка и подходами"
              />
              <svg
                viewBox="0 0 1000 1000"
                preserveAspectRatio="none"
                onClick={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  position(selected, {
                    x: Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)),
                    y: Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)),
                  });
                }}
              >
                {value.approaches.map((a) => (
                  <line
                    key={a.id}
                    x1={value.center.x * 1000}
                    y1={value.center.y * 1000}
                    x2={a.x * 1000}
                    y2={a.y * 1000}
                    stroke="white"
                    strokeWidth="4"
                    strokeDasharray="10 6"
                  />
                ))}
                {[
                  { id: "center", label: "Центр", ...value.center },
                  ...value.approaches,
                ].map((a, i) => (
                  <g key={a.id}>
                    <circle
                      cx={a.x * 1000}
                      cy={a.y * 1000}
                      r="20"
                      fill={a.id === selected ? "#f0bf61" : "white"}
                      stroke="#20262b"
                      strokeWidth="3"
                    />
                    <text
                      x={a.x * 1000}
                      y={a.y * 1000 + 8}
                      textAnchor="middle"
                      fontSize="24"
                      fill="#20262b"
                    >
                      {i || "Ц"}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
            <div className="topology-fields">
              <label>
                Тип перекрёстка
                <select
                  value={value.intersection_type}
                  onChange={(e) =>
                    onChange({ ...value, intersection_type: e.target.value })
                  }
                >
                  {Object.entries({
                    t: "Т-образный — 3 дороги",
                    y: "Y-образный — 3 дороги",
                    four_way: "Четырёхсторонний",
                    straight: "Прямой участок",
                    multi_way: "Многосторонний",
                  }).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              {[
                { id: "center", label: "Центр", ...value.center },
                ...value.approaches,
              ].map((a, i) => (
                <div className="topology-row" key={a.id}>
                  <button
                    aria-pressed={selected === a.id}
                    onClick={() => setSelected(a.id)}
                  >
                    {i || "Ц"}
                  </button>
                  <span>{a.label}</span>
                  {(["x", "y"] as const).map((axis) => (
                    <label key={axis}>
                      {axis.toUpperCase()}
                      <input
                        aria-label={`${a.label} ${axis.toUpperCase()}`}
                        type="number"
                        min="0"
                        max="1"
                        step="0.01"
                        value={Number(a[axis].toFixed(3))}
                        onChange={(e) =>
                          position(a.id, {
                            x: a.x,
                            y: a.y,
                            [axis]: Math.max(
                              0,
                              Math.min(1, Number(e.target.value)),
                            ),
                          })
                        }
                      />
                    </label>
                  ))}
                  {i > 0 && (
                    <button
                      aria-label={`Удалить подход ${i}`}
                      onClick={() => {
                        onChange({
                          ...value,
                          approaches: value.approaches.filter(
                            (v) => v.id !== a.id,
                          ),
                        });
                        setSelected("center");
                      }}
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              <button
                disabled={value.approaches.length >= 6}
                onClick={() =>
                  onChange({
                    ...value,
                    approaches: [
                      ...value.approaches,
                      {
                        id: `arm_${Date.now()}`,
                        label: `Подход ${value.approaches.length + 1}`,
                        x: 0.5,
                        y: 0.1,
                      },
                    ],
                  })
                }
              >
                Добавить подход
              </button>
            </div>
          </div>
          <div className="toolbar bottom">
            <button className="primary" disabled={busy} onClick={onSave}>
              Сохранить схему{project.result_run ? " и пересчитать" : ""}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
