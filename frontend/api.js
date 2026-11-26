export async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, options); }
  catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Нет связи с сервером. Проверьте запуск приложения и повторите действие.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({detail: response.statusText}));
    throw new Error(typeof body.detail === 'string' ? body.detail : 'Проверьте параметры: ' + JSON.stringify(body.detail));
  }
  return response.json();
}
export const jsonRequest = (method, body) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
export const categories = {pedestrian:'Пешеходы', bicycle:'Велосипеды', car:'Легковые', motorcycle:'Мотоциклы', bus:'Автобусы', truck:'Грузовые'};
export const statuses = {queued:'В очереди', running:'Идёт анализ', completed:'Завершён', failed:'Ошибка', cancelled:'Остановлен', stalled:'Обработчик не отвечает', review:'Проверить', confirmed:'Подтверждено', auto_accept:'Учтено', discarded:'Отклонено'};
export const timeLabel = value => `${Math.floor((value || 0)/60)}:${String(Math.floor((value || 0)%60)).padStart(2,'0')}`;
export const blankGeometry = () => ({mode:'automatic', entries:[], exits:[], roi:[]});
