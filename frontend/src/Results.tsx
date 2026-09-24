import { useEffect, useState } from "react";
import { ArrowUpRight, Download, AlertCircle, BarChart3 } from "lucide-react";
import { api, url, upload } from "./api";
import {
  classes,
  labels,
  timecode,
  type Project,
  type Interval,
} from "./types";
import VideoOverlay from "./VideoOverlay";
import Cartogram from "./Cartogram";
import AiAuditPanel from "./AiAudit";

type Metric = {
  manual: number;
  automatic: number;
  absolute_error: number;
  relative_error: number | null;
  within_threshold: boolean;
};
type Validation = {
  rows: (Metric & { movement_id: string; class: string })[];
  total: Metric & {
    sum_absolute_error: number;
    weighted_absolute_percentage_error: number | null;
  };
  by_class: Record<string, Metric>;
  by_movement: Record<string, Metric>;
  scope: string;
  unlabelled_cells: number;
};
export default function Results({
  project,
  onRefresh,
  onError,
}: {
  project: Project;
  onRefresh: () => void;
  onError: (s: string) => void;
}) {
  const r = project.result;
  const [minutes, setMinutes] = useState(15),
    [intervals, setIntervals] = useState<Interval[]>(r.intervals),
    [threshold, setThreshold] = useState(10),
    [validation, setValidation] = useState<Validation | null>(null),
    [uploading, setUploading] = useState(false),
    [renaming, setRenaming] = useState<string | null>(null),
    [newName, setNewName] = useState("");
  useEffect(() => {
    let disposed = false;
    api<Interval[]>(`/projects/${project.id}/intervals?minutes=${minutes}`)
      .then((v) => {
        if (!disposed) setIntervals(v);
      })
      .catch((e) => onError(e.message));
    return () => {
      disposed = true;
    };
  }, [minutes, project.id, project.result_run]);
  useEffect(() => {
    let disposed = false;
    if (project.ground_truth?.length)
      api<Validation>(
        `/projects/${project.id}/validation?threshold=${threshold}`,
      )
        .then((v) => {
          if (!disposed) setValidation(v);
        })
        .catch((e) => onError(e.message));
    return () => {
      disposed = true;
    };
  }, [threshold, project]);
  async function rename(id: string) {
    try {
      await api(`/projects/${project.id}/movements/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: newName }),
      });
      setRenaming(null);
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    }
  }
  async function truth(file?: File) {
    if (!file) return;
    setUploading(true);
    try {
      await upload(`/projects/${project.id}/ground-truth`, file, () => {});
      onRefresh();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setUploading(false);
    }
  }
  async function png() {
    try {
      const response = await fetch(url(`/projects/${project.id}/export/svg`));
      if (!response.ok) throw new Error("Не удалось загрузить картограмму");
      const blob = await response.blob();
      const object = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        const c = document.createElement("canvas");
        c.width = 1600;
        c.height = 1664;
        c.getContext("2d")!.drawImage(img, 0, 0, 1600, 1664);
        c.toBlob((b) => {
          if (b) {
            const href = URL.createObjectURL(b);
            const a = document.createElement("a");
            a.href = href;
            a.download = "cartogram.png";
            a.click();
            setTimeout(() => URL.revokeObjectURL(href), 1000);
          }
        });
        URL.revokeObjectURL(object);
      };
      img.onerror = () => {
        URL.revokeObjectURL(object);
        onError("Не удалось создать PNG");
      };
      img.src = object;
    } catch (e) {
      onError((e as Error).message);
    }
  }
  return (
    <div className="results">
      {project.status !== "completed" && (
        <div className="notice">
          <AlertCircle size={20} />
          <span>
            Показан последний успешно завершённый анализ. Новые результаты
            появятся после окончания обработки.
          </span>
        </div>
      )}
      <div className="stat-grid">
        {[
          ["Всего транспорта", r.total_vehicles, "Все направления"],
          ["Легковые", r.counts.car, "автомобилей"],
          ["Грузовые", r.counts.truck, "автомобилей"],
          ["Автобусы", r.counts.bus, "объектов"],
          ["Пешеходы", r.pedestrians, "отдельный подсчёт"],
          [
            "Время анализа",
            timecode(r.elapsed),
            r.device === "cpu" ? "Процессор · CPU" : `Устройство · ${r.device}`,
          ],
        ].map(([name, value, hint]) => (
          <div className="stat" key={name}>
            <span>{name}</span>
            <strong>
              {typeof value === "number" ? value.toLocaleString("ru") : value}
            </strong>
            <small>{hint}</small>
          </div>
        ))}
      </div>
      {!!r.diagnostics.unknown_tracks && (
        <div className="notice">
          <AlertCircle size={20} />
          <span>
            <strong>
              {r.diagnostics.unknown_tracks} объектов без определённого
              направления.
            </strong>{" "}
            Они учтены в итогах. Проверьте видео или задайте зоны въезда и
            выезда.
          </span>
        </div>
      )}
      <AiAuditPanel
        audit={r.ai_audit}
        localVlm={r.local_vlm}
        scene={r.scene_analysis}
        intersection={r.intersection}
      />
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Транспортные потоки</h2>
            <p>
              Распределение по направлениям за весь ролик ·{" "}
              {timecode(project.video.duration)}
            </p>
          </div>
          <div className="toolbar compact">
            {["xlsx", "csv", "json"].map((f) => (
              <a
                className={f === "xlsx" ? "button primary" : "button"}
                key={f}
                href={url(`/projects/${project.id}/export/${f}`)}
                download
              >
                <Download size={16} />
                {f.toUpperCase()}
              </a>
            ))}
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Направление</th>
                {classes.map((c) => (
                  <th key={c}>{labels[c]}</th>
                ))}
                <th>Всего ТС</th>
                <th>Проверка</th>
              </tr>
            </thead>
            <tbody>
              {r.movements.map((m) => (
                <tr key={m.id}>
                  <td>
                    {renaming === m.id ? (
                      <form
                        className="rename-form"
                        onSubmit={(e) => {
                          e.preventDefault();
                          void rename(m.id);
                        }}
                      >
                        <input
                          aria-label="Новое название направления"
                          value={newName}
                          onChange={(e) => setNewName(e.target.value)}
                          maxLength={120}
                        />
                        <button type="submit">OK</button>
                        <button type="button" onClick={() => setRenaming(null)}>
                          Отмена
                        </button>
                      </form>
                    ) : (
                      <button
                        className="text-button"
                        onClick={() => {
                          setRenaming(m.id);
                          setNewName(m.name);
                        }}
                      >
                        {m.name}
                        <ArrowUpRight size={13} />
                      </button>
                    )}
                    <small className="row-id">{m.id}</small>
                  </td>
                  {classes.map((c) => (
                    <td key={c}>{m.counts[c]}</td>
                  ))}
                  <td className="strong">{m.total}</td>
                  <td>
                    <span
                      className={`badge ${m.requires_review ? "review" : "completed"}`}
                    >
                      {m.requires_review ? "Проверить" : "Определено"} ·{" "}
                      {Math.round(m.reliability * 100)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Итого</td>
                {classes.map((c) => (
                  <td key={c}>{r.counts[c]}</td>
                ))}
                <td>{r.total_vehicles}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
        {!r.movements.length && (
          <div className="empty-small">
            Подтверждённых треков не найдено. Проверьте качество записи и
            попробуйте точный профиль.
          </div>
        )}
        <p className="hint">
          Всего ТС включает автомобили, автобусы, мотоциклы и велосипеды.
          Пешеходы считаются отдельно. Процент — геометрическая оценка
          надёжности направления, а не измеренная точность подсчёта.
        </p>
      </section>
      <div className="results-columns">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Картограмма</h2>
              <p>Условный вид сверху · значения за весь ролик</p>
            </div>
            <div className="toolbar compact">
              <a
                className="button"
                href={url(`/projects/${project.id}/export/svg`)}
                download
              >
                SVG
              </a>
              <button onClick={png}>PNG</button>
            </div>
          </div>
          <div className="cartogram">
            <Cartogram projectId={project.id} runId={project.result_run} />
          </div>
          {r.intersection?.requires_review && (
            <p className="notice">
              {r.intersection.review_reason || "Схема требует проверки"}
            </p>
          )}
          <div className="map-legend">
            {r.movements
              .filter((m) => m.id !== "unknown")
              .map((m) => (
                <span key={m.id}>
                  <i />
                  {m.name}{" "}
                  <b>
                    {m.total} ТС · {m.pedestrians} пеш.
                  </b>
                </span>
              ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Динамика потока</h2>
              <p>Время от начала записи</p>
            </div>
            <label className="inline-label">
              Интервал
              <select
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
              >
                {[5, 10, 15, 30, 60].map((v) => (
                  <option key={v} value={v}>
                    {v} мин
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="interval-chart">
            {intervals.map((v, i) => (
              <div className="chart-row" key={i}>
                <span>
                  {timecode(v.start)}–{timecode(v.end)}
                </span>
                <div className="bar-area">
                  <div
                    className="bar"
                    style={{
                      width: `${(v.total / Math.max(1, ...intervals.map((v) => v.total))) * 100}%`,
                    }}
                  />
                </div>
                <b>{v.total}</b>
              </div>
            ))}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Интервал</th>
                  <th>Транспорт</th>
                  <th>Пешеходы</th>
                </tr>
              </thead>
              <tbody>
                {intervals.map((v, i) => (
                  <tr key={i}>
                    <td>
                      {timecode(v.start)}–{timecode(v.end)}
                    </td>
                    <td>{v.total}</td>
                    <td>{v.pedestrians}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <VideoOverlay project={project} />
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Сравнение с ручным подсчётом</h2>
            <p>Загрузите CSV или XLSX с колонками movement_id, class, count</p>
          </div>
          <div className="toolbar compact">
            <a
              className="button"
              href={url(`/projects/${project.id}/ground-truth/template`)}
            >
              Скачать шаблон
            </a>
            <label className="button primary file-button">
              {uploading ? "Загрузка…" : "Загрузить эталон"}
              <input
                disabled={uploading}
                type="file"
                accept=".csv,.xlsx"
                aria-label="Загрузить ручной эталон"
                onChange={(e) => {
                  void truth(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </label>
          </div>
        </div>
        <div className="validation-content">
          <label className="inline-label">
            Порог ошибки, %{" "}
            <input
              type="number"
              min={0}
              max={1000}
              value={threshold}
              onChange={(e) =>
                setThreshold(
                  Math.max(0, Math.min(1000, Number(e.target.value))),
                )
              }
            />
          </label>
          {validation ? (
            <>
              <p>
                {validation.scope}. Незаданных ячеек:{" "}
                {validation.unlabelled_cells}.
              </p>
              <div className="validation-stats">
                <span>
                  Вручную <b>{validation.total.manual}</b>
                </span>
                <span>
                  Автоматически <b>{validation.total.automatic}</b>
                </span>
                <span>
                  Ошибка итога <b>{validation.total.absolute_error}</b>
                </span>
                <span>
                  Сумма ошибок <b>{validation.total.sum_absolute_error}</b>
                </span>
                <span>
                  WAPE{" "}
                  <b>
                    {validation.total.weighted_absolute_percentage_error?.toFixed(
                      1,
                    ) ?? "—"}
                    %
                  </b>
                </span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Направление / класс</th>
                      <th>Вручную</th>
                      <th>Авто</th>
                      <th>Абс. ошибка</th>
                      <th>Отн. ошибка</th>
                    </tr>
                  </thead>
                  <tbody>
                    {validation.rows.map((v) => (
                      <tr key={v.movement_id + v.class}>
                        <td>
                          {
                            r.movements.find((m) => m.id === v.movement_id)
                              ?.name
                          }{" "}
                          / {labels[v.class as keyof typeof labels]}
                        </td>
                        <td>{v.manual}</td>
                        <td>{v.automatic}</td>
                        <td>{v.absolute_error}</td>
                        <td className={!v.within_threshold ? "error-text" : ""}>
                          {v.relative_error === null
                            ? "Не определена (эталон 0)"
                            : `${v.relative_error.toFixed(1)}%`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <details>
                <summary>Ошибки по классам и направлениям</summary>
                {(
                  [
                    ["Классы", validation.by_class],
                    ["Направления", validation.by_movement],
                  ] as const
                ).map(([title, group]) => (
                  <div key={title}>
                    <h4>{title}</h4>
                    {Object.entries(group).map(([key, v]) => (
                      <p key={key}>
                        {labels[key as keyof typeof labels] ||
                          r.movements.find((m) => m.id === key)?.name ||
                          key}
                        : вручную {v.manual}, автоматически {v.automatic},
                        ошибка {v.absolute_error} (
                        {v.relative_error?.toFixed(1) ?? "не определена"}%)
                      </p>
                    ))}
                  </div>
                ))}
              </details>
            </>
          ) : (
            <div className="empty-small">
              <BarChart3 size={28} />
              <p>Проверьте результат на вашем эталоне</p>
              <span>
                Заполните шаблон ручными значениями. Незаполненные пары не
                считаются нулевыми.
              </span>
            </div>
          )}
        </div>
      </section>
      <details className="panel diagnostics">
        <summary>Сведения об анализе и диагностика</summary>
        <div className="metadata">
          {Object.entries({
            Модель: r.model,
            Устройство: r.device,
            "Размер кадра": `${project.video.width} × ${project.video.height}`,
            FPS: project.video.fps.toFixed(2),
            Обнаружений: r.diagnostics.detections,
            Треков: r.diagnostics.tracks,
            Определённых: r.diagnostics.completed_tracks,
            Неопределённых: r.diagnostics.unknown_tracks,
            "Коротких треков исключено": r.diagnostics.discarded_short_tracks,
            "Соединённых фрагментов": r.diagnostics.stitched_fragments,
          }).map(([key, v]) => (
            <div key={key}>
              <span>{key}</span>
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
