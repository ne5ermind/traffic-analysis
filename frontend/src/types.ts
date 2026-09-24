export const classes = [
  "car",
  "truck",
  "bus",
  "motorcycle",
  "bicycle",
  "pedestrian",
] as const;
export type ClassName = (typeof classes)[number];
export const labels: Record<ClassName, string> = {
  car: "Легковые",
  truck: "Грузовые",
  bus: "Автобусы",
  motorcycle: "Мотоциклы",
  bicycle: "Велосипеды",
  pedestrian: "Пешеходы",
};
export type Point = { x: number; y: number };
export type Zone = {
  id: string;
  name: string;
  kind: "entry" | "exit";
  points: Point[];
};
export type Line = { id: string; name: string; points: Point[] };
export type IntersectionConfig = {
  intersection_type: string;
  center: Point;
  approaches: (Point & { id: string; label: string })[];
};
export type Calibration = {
  zones: Zone[];
  lines: Line[];
  intersection?: IntersectionConfig | null;
};
export type Movement = {
  id: string;
  name: string;
  counts: Record<ClassName, number>;
  total: number;
  pedestrians: number;
  reliability: number;
  requires_review: boolean;
  ai_review_reason?: string;
  path: number[][];
  entry_zone?: string;
  exit_zone?: string;
};
export type AiAudit = {
  verdict: string;
  confidence: number;
  intersection: {
    type: string;
    approaches: string[];
    active_sides: string[];
    dominant_direction: string | null;
    confidence: number;
    route_count: number;
  };
  video_quality: {
    score: number;
    sharpness: number;
    brightness: number;
    contrast: number;
    detector_confidence: number;
    unknown_track_ratio: number;
    discarded_track_ratio: number;
    samples: number;
  };
  checks: { level: "ok" | "warning" | "error"; message: string }[];
  corrections_applied: string[];
};
export type LocalVlmReview = {
  status: "disabled" | "ok" | "unavailable";
  model: string;
  frames: number;
  message?: string;
  verdict?: string;
  confidence?: number;
  intersection_type?: string;
  approaches?: string[];
  dominant_directions?: string[];
  video_issues?: string[];
  suspect_movements?: {
    movement_id?: string;
    reason?: string;
    action?: string;
  }[];
  safe_corrections?: string[];
  explanation?: string;
};
export type Interval = Record<ClassName, number> & {
  start: number;
  end: number;
  total: number;
  pedestrians: number;
};
export type Results = {
  total_vehicles: number;
  pedestrians: number;
  counts: Record<ClassName, number>;
  movements: Movement[];
  intervals: Interval[];
  elapsed: number;
  device: string;
  model: string;
  diagnostics: Record<string, number>;
  calibration: Calibration;
  ai_audit?: AiAudit;
  local_vlm?: LocalVlmReview;
  scene_analysis?: SceneAnalysis;
  intersection?: SceneAnalysis & {
    source: string;
    requires_review: boolean;
    review_reason?: string;
  };
};
export type Project = {
  id: string;
  name: string;
  description: string;
  created_at: string;
  status: string;
  video: {
    filename?: string;
    width: number;
    height: number;
    duration: number;
    fps: number;
    codec: string;
    frame_count: number;
    file_size: number;
    warnings: string[];
  };
  config: Calibration;
  progress: {
    stage?: string;
    percent?: number;
    processed_frames?: number;
    total_frames?: number;
    elapsed?: number;
    eta?: number;
    device?: string;
    model?: string;
  };
  result: Results;
  result_run?: string;
  ground_truth: unknown[];
  error?: string;
  total_vehicles?: number;
};
export type Observation = {
  t: number;
  track_id: number;
  bbox: number[];
  point: number[];
  confidence: number;
  class_name: ClassName;
  movement_id: string;
  entry_zone?: string;
  exit_zone?: string;
};
export const statuses: Record<string, string> = {
  uploaded: "Готов к анализу",
  queued: "В очереди",
  processing: "Обработка",
  completed: "Завершён",
  failed: "Ошибка анализа",
  cancelled: "Отменён",
};
export const active = (p: Project) =>
  ["processing", "queued"].includes(p.status);
export function timecode(s: number = 0) {
  const n = Math.floor(s);
  return [Math.floor(n / 3600), Math.floor((n % 3600) / 60), n % 60]
    .map((v) => String(v).padStart(2, "0"))
    .join(":");
}

export type SceneAnalysis = {
  center?: Point;
  status?: "ok" | "disabled" | "unavailable";
  model?: string;
  frames?: number;
  message?: string;
  explanation?: string;
  intersection_type?: string;
  confidence?: number;
  fully_visible?: boolean;
  camera_static?: boolean;
  approaches?: {
    id: string;
    label: string;
    x: number;
    y: number;
    angle: number;
  }[];
};
