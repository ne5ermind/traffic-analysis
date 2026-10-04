import { useEffect, useRef, useState } from "react";
import { api, url } from "./api";
import { labels, type Observation, type Project } from "./types";

export default function VideoOverlay({ project }: { project: Project }) {
  const video = useRef<HTMLVideoElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const [bucket, setBucket] = useState(0),
    [rows, setRows] = useState<Observation[]>([]),
    [error, setError] = useState("");
  const [visible, setVisible] = useState({
    boxes: true,
    tracks: true,
    zones: true,
    labels: true,
  });
  useEffect(() => {
    let disposed = false;
    setRows([]);
    api<Observation[]>(
      `/projects/${project.id}/overlay?start=${bucket * 5}&seconds=5`,
    )
      .then((r) => {
        if (!disposed) {
          setRows(r);
          setError("");
        }
      })
      .catch((e) => {
        if (!disposed) setError(e.message);
      });
    return () => {
      disposed = true;
    };
  }, [bucket, project.id, project.result_run]);
  useEffect(() => {
    let raf = 0;
    function draw() {
      const v = video.current,
        c = canvas.current;
      if (v && c) {
        const ctx = c.getContext("2d")!;
        const w = c.width,
          h = c.height;
        ctx.clearRect(0, 0, w, h);
        const t = v.currentTime;
        ctx.lineWidth = 2;
        ctx.font = "14px system-ui";
        if (visible.zones) {
          for (const shape of [
            ...project.result.calibration.zones,
            ...project.result.calibration.lines,
          ]) {
            ctx.beginPath();
            shape.points.forEach((p, i) =>
              i ? ctx.lineTo(p.x * w, p.y * h) : ctx.moveTo(p.x * w, p.y * h),
            );
            if ("kind" in shape) ctx.closePath();
            ctx.strokeStyle = "#ffcc70";
            ctx.stroke();
            if (visible.labels) {
              ctx.fillStyle = "#ffcc70";
              ctx.fillText(
                shape.name,
                shape.points[0].x * w,
                shape.points[0].y * h - 8,
              );
            }
          }
        }
        const current = new Map<number, Observation>();
        for (const r of rows)
          if (r.t <= t && r.t >= t - Math.max(0.3, 3 / project.video.fps))
            current.set(r.track_id, r);
        for (const [id, r] of current) {
          const color = r.class_name === "pedestrian" ? "#ffc875" : "#71edbe";
          ctx.strokeStyle = color;
          const [x1, y1, x2, y2] = r.bbox;
          if (visible.boxes)
            ctx.strokeRect(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h);
          if (visible.tracks) {
            ctx.beginPath();
            const path = rows.filter(
              (p) => p.track_id === id && p.t <= t && p.t > t - 2,
            );
            path.forEach((p, i) =>
              i
                ? ctx.lineTo(p.point[0] * w, p.point[1] * h)
                : ctx.moveTo(p.point[0] * w, p.point[1] * h),
            );
            ctx.stroke();
          }
          if (visible.labels) {
            const movement =
              project.result.movements.find((m) => m.id === r.movement_id)
                ?.name || r.movement_id;
            const text = `#${id} ${labels[r.class_name]} · ${movement}${r.entry_zone ? " · " + r.entry_zone + " → " + (r.exit_zone || "?") : ""}`;
            const x = Math.max(
                0,
                Math.min(x1 * w, w - ctx.measureText(text).width - 10),
              ),
              y = Math.max(20, y1 * h - 5);
            ctx.fillStyle = "rgba(15,23,42,.86)";
            ctx.fillRect(x, y - 17, ctx.measureText(text).width + 10, 23);
            ctx.fillStyle = color;
            ctx.fillText(text, x + 5, y);
          }
        }
      }
      raf = requestAnimationFrame(draw);
    }
    draw();
    return () => cancelAnimationFrame(raf);
  }, [rows, visible, project]);
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Проверка на видео</h2>
          <p>Траектории, объекты и назначенные направления</p>
        </div>
      </div>
      <div className="video-wrap">
        <video
          ref={video}
          controls
          playsInline
          preload="metadata"
          poster={url(`/projects/${project.id}/media/preview`)}
          src={url(`/projects/${project.id}/media/playback`)}
          onTimeUpdate={() =>
            setBucket(Math.floor((video.current?.currentTime || 0) / 5))
          }
        />
        <canvas
          width={project.video.width}
          height={project.video.height}
          ref={canvas}
        />
      </div>
      <div className="toolbar">
        {(
          [
            ["boxes", "Объекты"],
            ["tracks", "Траектории"],
            ["zones", "Зоны"],
            ["labels", "Подписи"],
          ] as const
        ).map(([key, label]) => (
          <label className="check" key={key}>
            <input
              type="checkbox"
              checked={visible[key]}
              onChange={(e) =>
                setVisible({ ...visible, [key]: e.target.checked })
              }
            />
            {label}
          </label>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
