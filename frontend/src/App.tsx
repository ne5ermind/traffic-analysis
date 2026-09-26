import { useState, useEffect, useCallback } from "react";
import {
  Activity,
  FolderOpen,
  Plus,
  ArrowLeft,
  ArrowUpRight,
  Upload,
  Film,
  Play,
  Square,
  Trash2,
  Search,
  CheckCircle2,
  AlertCircle,
  FileSpreadsheet,
  Route,
  ChevronRight,
  X,
  LoaderCircle,
} from "lucide-react";
import { api, url, upload } from "./api";
import { active, statuses, timecode, type Project } from "./types";
import Calibration from "./Calibration";
import Results from "./Results";

type Health = {
  api: boolean;
  redis: boolean;
  workers: number;
  model: string;
  detector: string;
  local_ai?: {
    enabled: boolean;
    ready: boolean;
    models: string[];
    message?: string;
  };
};
function getRoute() {
  return location.hash.replace(/^#\/?/, "");
}
function navigate(path: string) {
  location.hash = "/" + path;
}
export default function App() {
  const [route, setRoute] = useState(getRoute),
    [projects, setProjects] = useState<Project[]>([]),
    [project, setProject] = useState<Project | null>(null),
    [health, setHealth] = useState<Health | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [search, setSearch] = useState(""),
    [tab, setTab] = useState("overview"),
    [profile, setProfile] = useState("balanced"),
    [busy, setBusy] = useState(false),
    [remove, setRemove] = useState(false);
  const id = route && route !== "new" ? route : null;
  useEffect(() => {
    const handler = () => {
      setRoute(getRoute());
      setTab("overview");
      setError("");
      setRemove(false);
      setProject(null);
      setLoading(true);
    };
    window.addEventListener("hashchange", handler);
    return () => window.removeEventListener("hashchange", handler);
  }, []);
  const refresh = useCallback(async () => {
    try {
      if (id) {
        const p = await api<Project>(`/projects/${id}`);
        setProject(p);
      } else setProjects(await api<Project[]>("/projects"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [id]);
  useEffect(() => {
    void refresh();
    const timer = setInterval(refresh, 2500);
    return () => clearInterval(timer);
  }, [refresh]);
  useEffect(() => {
    setProfile(project?.result?.profile ?? "balanced");
  }, [project?.id, project?.result_run]);
  useEffect(() => {
    const load = () =>
      api<Health>("/health")
        .then(setHealth)
        .catch(() => setHealth(null));
    void load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, []);
  async function action(path: string, body?: unknown, method = "POST") {
    setBusy(true);
    setError("");
    try {
      await api(`/projects/${id}${path}`, {
        method,
        body: body ? JSON.stringify(body) : undefined,
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteProject() {
    setBusy(true);
    try {
      await api(`/projects/${id}`, { method: "DELETE" });
      navigate("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setRemove(false);
    }
  }
  const completed = projects.filter((p) => p.status === "completed").length;
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#/" aria-label="InnovaTransport — проекты">
          <span className="brand-symbol">
            <Route size={26} />
          </span>
          <span>
            INNOVA<span className="brand-light">TRANSPORT</span>
          </span>
        </a>
        <div className="workspace-label">ТРАНСПОРТНАЯ АНАЛИТИКА</div>
        <nav>
          <a href="#/" className="nav-item selected">
            <FolderOpen size={19} /> Проекты{" "}
            <span>{projects.length || ""}</span>
          </a>
        </nav>
        <div className="sidebar-note">
          <div className="tiny-label">ОТ ВИДЕО К ДАННЫМ</div>
          <p>
            Транспортные потоки
            <br />
            для обоснованных решений.
          </p>
          <div className="mini-flow">
            <Film />
            <ChevronRight />
            <Activity />
            <ChevronRight />
            <FileSpreadsheet />
          </div>
        </div>
        <div className="system-status">
          <span
            className={
              "dot " + (health?.redis && health.workers ? "online" : "")
            }
          />
          <div>
            {health?.redis && health.workers
              ? "Система готова"
              : health?.redis
                ? "Ожидается обработчик"
                : "Нет связи с очередью"}
            <small>
              {health?.model?.split("/").pop() || "Проверка подключения"}
            </small>
            <small>
              {health?.local_ai?.ready
                ? "Qwen: обе модели доступны"
                : health?.local_ai?.enabled
                  ? "Qwen: нет подключения"
                  : "Qwen: выключены"}
            </small>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            Рабочее пространство <ChevronRight size={14} />{" "}
            <span>
              {id ? "Проект" : route === "new" ? "Новый проект" : "Проекты"}
            </span>
          </div>
          <a href="/api/docs" target="_blank" rel="noreferrer">
            Документация API <ArrowUpRight size={14} />
          </a>
        </header>
        <main>
          {error && (
            <div className="notice error" role="alert">
              <AlertCircle size={20} />
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Закрыть сообщение"
                onClick={() => setError("")}
              >
                <X size={18} />
              </button>
            </div>
          )}
          {route === "new" ? (
            <NewProject onError={setError} />
          ) : id ? (
            loading && !project ? (
              <div className="loading">
                <LoaderCircle /> Загрузка проекта…
              </div>
            ) : (
              project && (
                <>
                  <div className="page-heading">
                    <div>
                      <button
                        className="back-link"
                        onClick={() => navigate("")}
                      >
                        <ArrowLeft size={16} /> Все проекты
                      </button>
                      <div className="title-line">
                        <h1>{project.name}</h1>
                        <span className={"badge " + project.status}>
                          {project.video.filename
                            ? statuses[project.status]
                            : "Нет видео"}
                        </span>
                      </div>
                      <p>
                        {project.description ||
                          "Анализ транспортных потоков по видеозаписи"}
                      </p>
                    </div>
                    <button
                      className="icon-button danger"
                      disabled={active(project) || busy}
                      aria-label="Удалить проект"
                      onClick={() => setRemove(true)}
                    >
                      <Trash2 size={19} />
                    </button>
                  </div>
                  {remove && (
                    <div className="notice error">
                      <span>
                        Удалить «{project.name}» вместе с видео, траекториями и
                        результатами?
                      </span>
                      <button onClick={() => setRemove(false)}>Отмена</button>
                      <button
                        className="danger"
                        onClick={deleteProject}
                        disabled={busy}
                      >
                        Удалить всё
                      </button>
                    </div>
                  )}
                  <div
                    className="tabs"
                    role="tablist"
                    aria-label="Разделы проекта"
                  >
                    {[
                      ["overview", "Обзор"],
                      ["results", "Результаты"],
                      ["calibration", "Настройка направлений"],
                    ].map(([key, name]) => (
                      <button
                        role="tab"
                        aria-selected={tab === key}
                        key={key}
                        disabled={
                          (key === "results" && !project.result_run) ||
                          (key === "calibration" &&
                            (!project.video.filename || active(project)))
                        }
                        className={tab === key ? "current" : ""}
                        onClick={() => setTab(key)}
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                  {project.error && (
                    <div className="notice error" role="alert">
                      <AlertCircle />
                      <span>{project.error}</span>
                    </div>
                  )}
                  {active(project) && (
                    <section className="panel processing" aria-live="polite">
                      <div className="processing-head">
                        <span className="activity-icon">
                          <Activity />
                        </span>
                        <div>
                          <h2>
                            {project.status === "queued"
                              ? "Видео в очереди"
                              : {
                                  loading_model: "Загрузка модели",
                                  detecting: "Анализируем транспортные потоки",
                                  movements: "Определяем направления",
                                  scene_analysis:
                                    "Qwen3-VL определяет схему перекрёстка",
                                  scene_refinement:
                                    "Qwen3.5 уточняет геометрию дороги",
                                  ai_review:
                                    "Qwen3.5 проверяет кадры и результаты",
                                  preparing_video:
                                    "Подготавливаем видео для просмотра",
                                }[project.progress.stage || ""] ||
                                "Обработка видео"}
                          </h2>
                          <p>
                            {project.status === "queued"
                              ? "Обработка начнётся, когда освободится обработчик."
                              : "Можно оставить страницу открытой или вернуться позже."}
                          </p>
                        </div>
                        <strong>{project.progress.percent || 0}%</strong>
                      </div>
                      <progress
                        max={100}
                        value={project.progress.percent || 0}
                      />
                      <div className="progress-info">
                        <span>
                          Кадр{" "}
                          {project.progress.processed_frames?.toLocaleString(
                            "ru",
                          ) || 0}{" "}
                          /{" "}
                          {project.progress.total_frames?.toLocaleString("ru")}
                        </span>
                        <span>Прошло {timecode(project.progress.elapsed)}</span>
                        <span>
                          {project.progress.device === "cpu"
                            ? "CPU"
                            : project.progress.device
                              ? `GPU ${project.progress.device}`
                              : "Выбор устройства"}
                        </span>
                        {project.progress.eta != null && (
                          <span>
                            Около {timecode(project.progress.eta)} до конца
                            детекции
                          </span>
                        )}
                        <button
                          onClick={() => action("/analysis/cancel")}
                          disabled={busy}
                        >
                          <Square size={14} /> Отменить
                        </button>
                      </div>
                    </section>
                  )}
                  {tab === "overview" && (
                    <>
                      <div className="overview-grid">
                        <section className="panel video-card">
                          {project.video.filename ? (
                            <>
                              <video
                                controls
                                playsInline
                                poster={url(
                                  `/projects/${project.id}/media/preview`,
                                )}
                                src={url(
                                  `/projects/${project.id}/media/${project.result_run ? "playback" : "source"}`,
                                )}
                              />
                              <div className="video-caption">
                                <Film size={18} />
                                <span>{project.video.filename}</span>
                                <small>
                                  {(
                                    project.video.file_size /
                                    1024 /
                                    1024
                                  ).toFixed(1)}{" "}
                                  МБ
                                </small>
                              </div>
                            </>
                          ) : (
                            <ReplaceVideo
                              project={project}
                              onDone={refresh}
                              onError={setError}
                            />
                          )}
                        </section>
                        <section className="panel analysis-settings">
                          <div className="eyebrow">АВТОМАТИЧЕСКИЙ АНАЛИЗ</div>
                          <h2>
                            {active(project)
                              ? "Анализ выполняется"
                              : project.result_run
                              ? "Анализ готов"
                              : "От записи к потокам"}
                          </h2>
                          <p>
                            Система распознает транспорт и пешеходов, построит
                            траектории и посчитает направления.
                          </p>
                          <label>
                            Режим обработки
                            <select
                              value={profile}
                              onChange={(e) => setProfile(e.target.value)}
                              disabled={active(project)}
                            >
                              <option value="fast">Быстрый</option>
                              <option value="balanced">Сбалансированный</option>
                              <option value="accurate">Точный</option>
                            </select>
                          </label>
                          <p className="hint">
                            {profile === "fast"
                              ? "Быстрее обрабатывает запись. Лучше для крупных объектов и хорошего обзора."
                              : profile === "accurate"
                                ? "Больше деталей для небольших объектов. Потребуется больше времени."
                                : "Баланс детализации и времени обработки для большинства записей."}
                          </p>
                          <div className="model-info">
                            <span>Модель</span>
                            <strong>{health?.model || "—"}</strong>
                          </div>
                          <button
                            className="primary full"
                            disabled={
                              !project.video.filename || active(project) || busy
                            }
                            onClick={() => action("/analysis", { profile })}
                          >
                            <Play size={17} />
                            {project.result_run
                              ? "Запустить заново"
                              : "Запустить анализ"}
                          </button>
                          {project.result_run && (
                            <button
                              className="full"
                              onClick={() => setTab("results")}
                            >
                              Открыть результаты <ArrowUpRight size={16} />
                            </button>
                          )}
                          <small>
                            Зоны необязательны: направления определяются
                            автоматически.
                          </small>
                        </section>
                      </div>
                      {project.video.filename && (
                        <section className="panel">
                          <div className="panel-heading">
                            <h2>Параметры записи</h2>
                            <ReplaceVideo
                              project={project}
                              onDone={refresh}
                              onError={setError}
                              compact
                            />
                          </div>
                          <div className="metadata">
                            {Object.entries({
                              Разрешение: `${project.video.width} × ${project.video.height}`,
                              Длительность: timecode(project.video.duration),
                              "Частота кадров": `${project.video.fps.toFixed(2)} FPS`,
                              Кодек: project.video.codec,
                              Кадров:
                                project.video.frame_count.toLocaleString("ru"),
                              Загружено: new Date(
                                project.created_at,
                              ).toLocaleDateString("ru"),
                            }).map(([k, v]) => (
                              <div key={k}>
                                <span>{k}</span>
                                <strong>{v}</strong>
                              </div>
                            ))}
                          </div>
                          {project.video.warnings?.length > 0 && (
                            <div className="notice">
                              <AlertCircle size={20} />
                              <span>
                                {project.video.warnings.join(". ")}. Качество
                                записи может снизить точность подсчёта.
                              </span>
                            </div>
                          )}
                        </section>
                      )}
                      {project.result_run && (
                        <div className="ready-banner">
                          <CheckCircle2 />
                          <div>
                            <h3>Результаты доступны</h3>
                            <p>
                              {project.result.total_vehicles} транспортных
                              средств · {project.result.pedestrians} пешеходов ·{" "}
                              {
                                project.result.movements.filter(
                                  (m) => m.id !== "unknown",
                                ).length
                              }{" "}
                              направлений
                            </p>
                          </div>
                          <button
                            className="primary"
                            onClick={() => setTab("results")}
                          >
                            Посмотреть результаты <ArrowUpRight size={16} />
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {tab === "results" && project.result_run && (
                    <Results
                      project={project}
                      onRefresh={refresh}
                      onError={setError}
                    />
                  )}
                  {tab === "calibration" && (
                    <Calibration
                      key={project.id}
                      project={project}
                      onSaved={() => {
                        void refresh();
                        setTab("overview");
                      }}
                      onError={setError}
                    />
                  )}
                </>
              )
            )
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ВИДЕОАНАЛИТИКА</div>
                  <h1>Транспортные потоки</h1>
                  <p>
                    Загрузите видео перекрёстка. Получите направления, подсчёт и
                    готовый отчёт.
                  </p>
                </div>
                <button className="primary" onClick={() => navigate("new")}>
                  <Plus size={18} /> Новый проект
                </button>
              </div>
              <div className="summary-strip">
                <div>
                  <FolderOpen />
                  <span>
                    Всего проектов<strong>{projects.length}</strong>
                  </span>
                </div>
                <div>
                  <CheckCircle2 />
                  <span>
                    Завершено<strong>{completed}</strong>
                  </span>
                </div>
                <div>
                  <Activity />
                  <span>
                    В обработке<strong>{projects.filter(active).length}</strong>
                  </span>
                </div>
                <div>
                  <Route />
                  <span>
                    Транспорт учтён
                    <strong>
                      {projects
                        .reduce((s, p) => s + (p.total_vehicles || 0), 0)
                        .toLocaleString("ru")}
                    </strong>
                  </span>
                </div>
              </div>
              <section className="panel project-list">
                <div className="panel-heading">
                  <h2>
                    Мои проекты <span className="count">{projects.length}</span>
                  </h2>
                  <label className="search">
                    <Search size={17} />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Поиск по названию"
                      aria-label="Поиск проектов"
                    />
                  </label>
                </div>
                {loading ? (
                  <div className="loading">Загрузка проектов…</div>
                ) : projects.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Проект</th>
                          <th>Дата создания</th>
                          <th>Видео</th>
                          <th>Статус</th>
                          <th>Транспорт</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {projects
                          .filter((p) =>
                            p.name.toLowerCase().includes(search.toLowerCase()),
                          )
                          .map((p) => (
                            <tr key={p.id}>
                              <td>
                                <a className="project-name" href={`#/${p.id}`}>
                                  <span className="project-thumb">
                                    {p.video.filename ? (
                                      <img
                                        src={url(
                                          `/projects/${p.id}/media/preview`,
                                        )}
                                        alt=""
                                      />
                                    ) : (
                                      <Film size={22} />
                                    )}
                                  </span>
                                  <div>
                                    <strong>{p.name}</strong>
                                    <small>
                                      {p.description || "Транспортный анализ"}
                                    </small>
                                  </div>
                                </a>
                              </td>
                              <td>
                                {new Date(p.created_at).toLocaleDateString(
                                  "ru",
                                )}
                              </td>
                              <td>
                                {p.video.filename
                                  ? timecode(p.video.duration)
                                  : "Не загружено"}
                              </td>
                              <td>
                                <span className={"badge " + p.status}>
                                  {p.video.filename
                                    ? statuses[p.status]
                                    : "Нет видео"}
                                </span>
                              </td>
                              <td className="strong">
                                {p.total_vehicles?.toLocaleString("ru") ?? "—"}
                              </td>
                              <td>
                                <a
                                  className="icon-button"
                                  href={`#/${p.id}`}
                                  aria-label={`Открыть ${p.name}`}
                                >
                                  <ArrowUpRight size={18} />
                                </a>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty-state">
                    <div className="empty-illustration">
                      <Film size={40} />
                      <span>
                        <Route size={24} />
                      </span>
                    </div>
                    <h2>Первый шаг — видеозапись</h2>
                    <p>
                      Создайте проект и загрузите видео.
                      <br />
                      Всё остальное система посчитает автоматически.
                    </p>
                    <button className="primary" onClick={() => navigate("new")}>
                      <Plus size={17} /> Создать первый проект
                    </button>
                    <div className="onboarding-steps">
                      <span>
                        <b>01</b> Загрузите видео
                      </span>
                      <ChevronRight size={14} />
                      <span>
                        <b>02</b> Запустите анализ
                      </span>
                      <ChevronRight size={14} />
                      <span>
                        <b>03</b> Скачайте Excel
                      </span>
                    </div>
                  </div>
                )}
              </section>
              <div className="footnote">
                <AlertCircle size={16} /> Автоматический подсчёт помогает
                сократить ручную работу. Проверяйте сложные направления по видео
                и эталону.
              </div>
            </>
          )}
        </main>
        <footer>
          InnovaTransport <span>Анализ транспортных потоков · v1.0</span>
        </footer>
      </div>
    </div>
  );
}
function NewProject({ onError }: { onError: (s: string) => void }) {
  const [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [percent, setPercent] = useState(0),
    [created, setCreated] = useState<string | null>(null);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    try {
      let id = created;
      if (!id) {
        const p = await api<Project>("/projects", {
          method: "POST",
          body: JSON.stringify({ name, description }),
        });
        id = p.id;
        setCreated(id);
      }
      await upload(`/projects/${id}/video`, file, setPercent);
      navigate(id);
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <button className="back-link" onClick={() => navigate("")}>
        <ArrowLeft size={16} /> Все проекты
      </button>
      <div className="page-heading">
        <div>
          <h1>Новый проект</h1>
          <p>Один проект — одна видеозапись транспортного узла.</p>
        </div>
      </div>
      <form className="panel new-project" onSubmit={submit}>
        <div className="form-section">
          <h2>О проекте</h2>
          <label>
            Название проекта
            <input
              required
              maxLength={200}
              value={name}
              disabled={busy || !!created}
              onChange={(e) => setName(e.target.value)}
              placeholder="Например, перекрёсток Ленина — Мира"
            />
          </label>
          <label>
            Описание <span className="muted">необязательно</span>
            <textarea
              maxLength={4000}
              value={description}
              disabled={busy || !!created}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Место съёмки, дата, время наблюдения"
            />
          </label>
        </div>
        <div className="form-section">
          <h2>Видеозапись</h2>
          <label
            className="dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (!busy && e.dataTransfer.files[0])
                setFile(e.dataTransfer.files[0]);
            }}
          >
            <Upload size={28} />
            <strong>{file?.name || "Выберите или перетащите видео"}</strong>
            <span>
              {file
                ? `${(file.size / 1024 / 1024).toFixed(1)} МБ`
                : "MP4, MOV, MKV, AVI, WebM, M4V, MTS, M2TS · любое разрешение"}
            </span>
            <input
              type="file"
              accept=".mp4,.mov,.m4v,.mkv,.avi,.webm,.mts,.m2ts"
              required={!file}
              disabled={busy}
              aria-label="Выбрать видео"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <span className="button">Выбрать файл</span>
          </label>
          <p className="hint">
            Лучше всего подходит неподвижная камера с обзором въездов и выездов.
            Система проверит качество записи после загрузки.
          </p>
        </div>
        {busy && (
          <div className="upload-progress" aria-live="polite">
            <progress max={100} value={percent} />
            <span>
              {percent === 100
                ? "Проверяем видео…"
                : `Загружаем видео: ${percent}%`}
            </span>
          </div>
        )}
        <div className="form-footer">
          <button type="button" disabled={busy} onClick={() => navigate("")}>
            Отмена
          </button>
          <button
            className="primary"
            disabled={busy || !file || !name.trim()}
            type="submit"
          >
            {busy
              ? "Создаём проект…"
              : created
                ? "Повторить загрузку"
                : "Создать проект"}
            <ArrowUpRight size={16} />
          </button>
        </div>
      </form>
    </>
  );
}
function ReplaceVideo({
  project,
  onDone,
  onError,
  compact = false,
}: {
  project: Project;
  onDone: () => void;
  onError: (s: string) => void;
  compact?: boolean;
}) {
  const [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [chosen, setChosen] = useState<File | null>(null);
  async function send(file: File) {
    setBusy(true);
    try {
      await upload(`/projects/${project.id}/video`, file, setProgress);
      setChosen(null);
      onDone();
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={compact ? "replace-video" : "empty-state"}>
      {chosen && project.video.filename ? (
        <>
          <span className="hint">Замена удалит текущие результаты и зоны.</span>
          <button disabled={busy} onClick={() => send(chosen)}>
            Заменить видео
          </button>
          <button disabled={busy} onClick={() => setChosen(null)}>
            Отмена
          </button>
        </>
      ) : (
        <label className="button file-button">
          <Upload size={16} />
          {busy
            ? `${progress}% · проверка видео`
            : compact
              ? "Заменить видео"
              : "Загрузить видео"}
          <input
            type="file"
            accept=".mp4,.mov,.m4v,.mkv,.avi,.webm,.mts,.m2ts"
            disabled={busy || active(project)}
            aria-label="Загрузить видео в проект"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) {
                if (project.video.filename) setChosen(f);
                else void send(f);
              }
              e.target.value = "";
            }}
          />
        </label>
      )}
    </div>
  );
}
