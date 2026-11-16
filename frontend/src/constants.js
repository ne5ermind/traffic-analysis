export const labels = {
  car: 'Легковой автомобиль',
  truck: 'Грузовой автомобиль',
  bus: 'Автобус',
  motorcycle: 'Мотоцикл',
  bicycle: 'Велосипед',
  pedestrian: 'Пешеход',
  review: 'Проверить',
  confirmed: 'Подтверждено',
  auto_accept: 'Учтено',
  discarded: 'Отклонено',
};

export const runLabels = {
  queued: 'В очереди',
  running: 'Идёт анализ',
  completed: 'Завершён',
  failed: 'Ошибка',
  cancelled: 'Остановлен',
  stalled: 'Worker не отвечает',
};

export const activeRunStatuses = ['queued', 'running', 'stalled'];
export const blankGeometry = () => ({entries: [], exits: [], roi: []});
