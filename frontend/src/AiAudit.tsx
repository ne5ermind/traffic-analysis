import type { AiAudit, LocalVlmReview, SceneAnalysis } from "./types";

const kinds: Record<string, string> = {
  t: "Т-образный",
  y: "Y-образный",
  four_way: "Четырёхсторонний",
  straight: "Прямой участок",
  roundabout: "Кольцевой",
  multi_way: "Многосторонний",
  unknown: "Не определён",
};
const verdicts: Record<string, string> = {
  ok: "В выборке замечаний нет",
  review: "Нужна проверка",
  low_quality: "Низкое качество видео",
};
export default function AiAuditPanel({
  audit,
  localVlm,
  scene,
  intersection,
}: {
  audit?: AiAudit;
  localVlm?: LocalVlmReview;
  scene?: SceneAnalysis;
  intersection?: SceneAnalysis & {
    source: string;
    requires_review: boolean;
    review_reason?: string;
  };
}) {
  if (!audit && !localVlm && !scene) return null;
  return (
    <section className="panel ai-audit">
      <div className="panel-heading">
        <div>
          <h2>Проверка нейросетями</h2>
          <p>Локальный анализ выбранных кадров и результатов детектора</p>
        </div>
      </div>
      <div className="audit-grid">
        <div>
          <span>Тип перекрёстка</span>
          <strong>
            {kinds[intersection?.intersection_type || "unknown"] ||
              "Не определён"}
          </strong>
        </div>
        <div>
          <span>Видимые подходы</span>
          <strong>
            {intersection?.approaches?.map((a) => a.label).join(" · ") ||
              "Не определены"}
          </strong>
        </div>
        <div>
          <span>Источник схемы</span>
          <strong>
            {intersection?.source === "calibration" ||
            intersection?.source === "manual"
              ? "Ваша калибровка"
              : scene?.status === "ok"
                ? scene.model
                : "Нет данных"}
          </strong>
        </div>
        <div>
          <span>Визуальная проверка</span>
          <strong>
            {localVlm?.status === "ok"
              ? verdicts[localVlm.verdict || "review"]
              : "Не выполнена"}
          </strong>
        </div>
      </div>
      {[
        { title: "Геометрия дороги", value: scene },
        { title: "Проверка обнаружений", value: localVlm },
      ].map(({ title, value }) => (
        <div className="local-vlm-result" key={title}>
          <strong>
            {title} · {value?.model || "модель не подключена"}
          </strong>
          {value?.status === "ok" ? (
            <>
              <p>{value.explanation}</p>
              <small>
                Проверено кадров: {value.frames}. Самооценка модели:{" "}
                {Math.round((value.confidence || 0) * 100)}% — это не измеренная
                точность.
              </small>
            </>
          ) : (
            <p>
              {value?.message ||
                (value?.status === "disabled"
                  ? "Локальная модель выключена в настройках сервиса."
                  : "Для этого результата нейросеть не запускалась. Повторите анализ.")}
            </p>
          )}
        </div>
      ))}
      {!!localVlm?.video_issues?.length && (
        <ul>
          {localVlm.video_issues.map((v, i) => (
            <li key={i}>{v}</li>
          ))}
        </ul>
      )}
      {!!localVlm?.suspect_movements?.length && (
        <ul>
          {localVlm.suspect_movements.map((v, i) => (
            <li key={i}>
              <b>{v.movement_id}</b>: {v.reason}
            </li>
          ))}
        </ul>
      )}
      <p className="hint">
        Выборка кадров помогает найти проблемы, но не подтверждает точность
        подсчёта всего видео. Нейросети не добавляют и не удаляют машины по
        догадке. Для оценки ошибки используйте сравнение с ручным подсчётом
        ниже.
      </p>
      {audit && (
        <details>
          <summary>Диагностика качества и согласованности</summary>
          <p className="hint">
            Автоматические эвристики по изображению и трекам. Не заключение
            нейросети.
          </p>
          <ul className="audit-checks">
            {audit.checks.map((c, i) => (
              <li className={`audit-check ${c.level}`} key={i}>
                {c.message}
              </li>
            ))}
          </ul>
          {!!audit.corrections_applied.length && (
            <p>{audit.corrections_applied.join("; ")}</p>
          )}
        </details>
      )}
    </section>
  );
}
