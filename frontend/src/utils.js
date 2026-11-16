export function formatTime(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  return `${Math.floor(value / 60)}:${String(value % 60).padStart(2, '0')}`;
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function cloneGeometry(geometry) {
  return structuredClone(geometry);
}
