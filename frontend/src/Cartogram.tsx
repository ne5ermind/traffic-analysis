import { url } from "./api";

export default function Cartogram({
  projectId,
  runId,
}: {
  projectId: string;
  runId?: string;
}) {
  return (
    <img
      className="cartogram-image"
      src={url(`/projects/${projectId}/export/svg?run=${runId || ""}`)}
      alt="Картограмма: стрелки направлений, количество транспорта, суммы въезда и выезда"
    />
  );
}
