import {useCallback, useEffect, useRef} from 'react';
import {labels} from '../constants.js';

export function useOverlayCanvas({traffic}) {
  const canvasRef = useRef(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * ratio);
    canvas.height = Math.round(rect.height * ratio);
    const context = canvas.getContext('2d');
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, rect.width, rect.height);
    const width = rect.width, height = rect.height;
    let savedGeometry = null;
    if (traffic.view === 'analysis' && traffic.run) savedGeometry = JSON.parse(traffic.run.geometry);
    else if (traffic.mode === 'manual') savedGeometry = traffic.geometry;
    const line = (points, color, fill = false) => {
      if (!points?.length) return;
      context.beginPath();
      points.forEach(([x, y], index) => index ? context.lineTo(x * width, y * height) : context.moveTo(x * width, y * height));
      if (fill && points.length >= 3) { context.closePath(); context.fillStyle = '#38bdf833'; context.fill(); }
      context.lineWidth = 3; context.strokeStyle = color; context.stroke();
      points.forEach(([x, y]) => { context.beginPath(); context.arc(x * width, y * height, 5, 0, Math.PI * 2); context.fillStyle = color; context.fill(); });
    };
    if (savedGeometry) {
      line(savedGeometry.roi, '#38bdf8', true);
      (savedGeometry.entries || []).forEach(item => line(item.points, '#fbbf24'));
      (savedGeometry.exits || []).forEach(item => line(item.points, '#22d3ee'));
    }
    if (traffic.view === 'setup' && traffic.mode === 'manual') line(traffic.pending, '#fb7185');
    if (traffic.view !== 'analysis') return;
    traffic.detections.forEach(object => {
      const [x1, y1, x2, y2] = object.box;
      const recorded = traffic.events.find(event => event.tracker_id === object.id && event.status !== 'discarded');
      const category = recorded?.category || object.category;
      const color = category === 'pedestrian' ? '#fbbf24' : category === 'car' ? '#60a5fa' : '#22d3ee';
      const x = x1 * width, y = y1 * height, boxWidth = (x2 - x1) * width, boxHeight = (y2 - y1) * height;
      context.strokeStyle = color; context.lineWidth = 2; context.strokeRect(x, y, boxWidth, boxHeight);
      const text = `${labels[category] || category} · #${object.id}`;
      context.font = '600 12px system-ui, sans-serif';
      const tagWidth = Math.min(context.measureText(text).width + 14, width);
      const tagX = Math.max(0, Math.min(x, width - tagWidth));
      const tagY = y > 24 ? y - 23 : y;
      context.fillStyle = '#061a31eb'; context.fillRect(tagX, tagY, tagWidth, 21);
      context.fillStyle = color; context.fillText(text, tagX + 7, tagY + 15, tagWidth - 12);
    });
  }, [traffic]);

  useEffect(() => { draw(); }, [draw]);
  useEffect(() => { window.addEventListener('resize', draw); return () => window.removeEventListener('resize', draw); }, [draw]);
  return {canvasRef, draw};
}
