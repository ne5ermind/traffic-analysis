export function WorkspaceHeader() {
  return <section className="workspace-head" aria-labelledby="workspaceHeading">
    <div><span className="eyebrow">ПАНЕЛЬ АНАЛИТИКА</span><h1 id="workspaceHeading">Анализ транспортного потока</h1><p>Один рабочий процесс: источник записи, зона подсчёта и готовый отчёт.</p></div>
    <ol className="workflow" aria-label="Этапы работы"><li><span>1</span>Видео</li><li><span>2</span>Зона</li><li><span>3</span>Результат</li></ol>
  </section>;
}
