import {useCallback, useEffect, useRef, useState} from 'react';
import {api, jsonRequest} from '../api.js';
import {activeRunStatuses, blankGeometry} from '../constants.js';
import {clamp, cloneGeometry} from '../utils.js';

export function useTrafficAnalysis(flash) {
  const [videos, setVideos] = useState([]);
  const [scenes, setScenes] = useState([]);
  const [runs, setRuns] = useState([]);
  const [events, setEvents] = useState([]);
  const [video, setVideo] = useState(null);
  const [scene, setScene] = useState(null);
  const [run, setRun] = useState(null);
  const [mode, setModeState] = useState('automatic');
  const [view, setView] = useState('setup');
  const [tool, setToolState] = useState('entry');
  const [geometry, setGeometry] = useState(blankGeometry);
  const [pending, setPending] = useState([]);
  const [dirty, setDirty] = useState(false);
  const [detections, setDetections] = useState([]);
  const [result, setResult] = useState(null);
  const [intervalMinutes, setIntervalMinutes] = useState(15);
  const [topology, setTopology] = useState('auto');
  const [cartogramTopology, setCartogramTopology] = useState('auto');
  const [profile, setProfile] = useState('fast');
  const [sampleFps, setSampleFps] = useState(6);
  const [sceneName, setSceneNameState] = useState('Моя зона');
  const [lineName, setLineName] = useState('Север');
  const [busy, setBusy] = useState('');
  const [uploadStatus, setUploadStatus] = useState('MP4, MOV, MKV, AVI или WebM');
  const [dialogEvent, setDialogEvent] = useState(undefined);
  const videoRef = useRef(null);
  const requestRef = useRef(0);
  const lastDetectionRef = useRef(0);
  const runRef = useRef(run);
  const videoRefState = useRef(video);
  const viewRef = useRef(view);

  useEffect(() => { runRef.current = run; }, [run]);
  useEffect(() => { videoRefState.current = video; }, [video]);
  useEffect(() => { viewRef.current = view; }, [view]);

  const guarded = useCallback(async action => {
    try { return await action(); }
    catch (error) { flash(error.message || String(error)); return undefined; }
  }, [flash]);

  const loadVideos = useCallback(async () => {
    const data = await api('/api/videos');
    setVideos(data);
    return data;
  }, []);

  const loadScenes = useCallback(async (selectedVideo = videoRefState.current, selectedScene = scene) => {
    if (!selectedVideo) { setScenes([]); return []; }
    const data = (await api(`/api/scenes?video_id=${selectedVideo.id}`))
      .filter(item => item.geometry.mode !== 'automatic');
    setScenes(data);
    if (selectedScene) setScene(data.find(item => item.id === selectedScene.id) || null);
    return data;
  }, [scene]);

  const loadRuns = useCallback(async (selectedVideo = videoRefState.current) => {
    if (!selectedVideo) { setRuns([]); return []; }
    const data = await api(`/api/runs?video_id=${selectedVideo.id}`);
    setRuns(data);
    const current = runRef.current;
    if (current) {
      const refreshed = data.find(item => item.id === current.id) || null;
      setRun(refreshed);
      runRef.current = refreshed;
    }
    return data;
  }, []);

  const refreshReport = useCallback(async (selectedRun = runRef.current) => {
    if (!selectedRun) { setResult(null); return null; }
    const interval = clamp(Number(intervalMinutes) || 15, 1, 1440) * 60;
    const data = await api(`/api/runs/${selectedRun.id}/results?interval=${interval}`);
    if (runRef.current?.id !== selectedRun.id) return null;
    setEvents(data.events);
    setResult(data);
    return data;
  }, [intervalMinutes]);

  const loadDetections = useCallback(async (force = false) => {
    const selectedRun = runRef.current;
    if (viewRef.current !== 'analysis' || !selectedRun || !videoRefState.current) return;
    if (!force && performance.now() - lastDetectionRef.current < 250) return;
    lastDetectionRef.current = performance.now();
    const request = ++requestRef.current;
    try {
      const time = Math.max(0, videoRef.current?.currentTime || 0);
      const frame = await api(`/api/runs/${selectedRun.id}/results?view=detections&time_s=${time}`);
      if (request === requestRef.current && runRef.current?.id === selectedRun.id && viewRef.current === 'analysis') {
        setDetections(frame.objects);
      }
    } catch {
      if (request === requestRef.current) setDetections([]);
    }
  }, []);

  const selectRun = useCallback(async (id, availableRuns = runs, availableScenes = scenes) => {
    const selected = availableRuns.find(item => item.id === id);
    if (!selected) return;
    setRun(selected);
    runRef.current = selected;
    setView('analysis');
    viewRef.current = 'analysis';
    setDetections([]);
    requestRef.current += 1;
    const savedGeometry = JSON.parse(selected.geometry);
    setCartogramTopology(savedGeometry.topology || 'auto');
    if (savedGeometry.mode !== 'automatic') {
      const selectedScene = availableScenes.find(item => item.id === selected.scene_id) || null;
      setScene(selectedScene);
      if (selectedScene) {
        setGeometry(cloneGeometry(selectedScene.geometry));
        setSceneNameState(selectedScene.name);
      }
    }
    setModeState(savedGeometry.mode === 'automatic' ? 'automatic' : 'manual');
    await refreshReport(selected);
    await loadDetections(true);
  }, [loadDetections, refreshReport, runs, scenes]);

  const selectVideo = useCallback(async id => {
    const selected = videos.find(item => item.id === id);
    if (!selected) return;
    setVideo(selected);
    videoRefState.current = selected;
    setScene(null); setRun(null); runRef.current = null;
    setGeometry(blankGeometry()); setPending([]); setDetections([]); setEvents([]); setResult(null);
    setDirty(false); setView('setup'); viewRef.current = 'setup'; requestRef.current += 1;
    setTopology('auto'); setSceneNameState('Моя зона'); setModeState('automatic');
    const availableScenes = await loadScenes(selected, null);
    const availableRuns = await loadRuns(selected);
    if (availableRuns.length) await selectRun(availableRuns[0].id, availableRuns, availableScenes);
  }, [loadRuns, loadScenes, selectRun, videos]);

  const selectScene = useCallback(id => {
    const selected = scenes.find(item => item.id === id) || null;
    setScene(selected);
    setGeometry(selected ? cloneGeometry(selected.geometry) : blankGeometry());
    setPending([]); setDirty(false); setView('setup'); viewRef.current = 'setup';
    setDetections([]); requestRef.current += 1;
    setSceneNameState(selected?.name || 'Моя зона'); setModeState('manual');
  }, [scenes]);

  const changeMode = useCallback(nextMode => {
    setModeState(nextMode); setView('setup'); viewRef.current = 'setup';
    setDetections([]); requestRef.current += 1;
  }, []);

  const setTool = useCallback(nextTool => { setToolState(nextTool); setPending([]); }, []);

  const addPoint = useCallback(point => {
    if (!video || mode !== 'manual') return;
    setView('setup'); viewRef.current = 'setup'; setDetections([]); requestRef.current += 1;
    setPending(current => {
      const next = [...current, point];
      if (tool === 'roi' || next.length < 2) return next;
      const kind = tool === 'entry' ? 'entries' : 'exits';
      const name = lineName.trim();
      if (!name || geometry[kind].some(item => item.name === name)) {
        flash(!name ? 'Введите название линии' : 'Название линии уже используется в этом направлении');
        return [];
      }
      setGeometry(currentGeometry => ({
        ...currentGeometry,
        [kind]: [...currentGeometry[kind], {name, points: next}],
      }));
      setDirty(true);
      return [];
    });
  }, [flash, geometry, lineName, mode, tool, video]);

  const finishRoi = useCallback(() => {
    if (pending.length < 3) { flash('Отметьте минимум три точки области'); return; }
    setGeometry(current => ({...current, roi: pending})); setPending([]); setDirty(true);
  }, [flash, pending]);

  const removeGeometry = useCallback((kind, index) => {
    setGeometry(current => {
      if (kind === 'roi') return {...current, roi: []};
      return {...current, [kind]: current[kind].filter((_, itemIndex) => itemIndex !== index)};
    });
    setDirty(true);
  }, []);

  const setSceneName = useCallback(value => { setSceneNameState(value); setDirty(true); }, []);

  const uploadVideo = useCallback(file => guarded(async () => {
    if (!file) return;
    setBusy('upload'); setUploadStatus('Загрузка видео…');
    const form = new FormData(); form.append('file', file);
    try {
      const uploaded = await api('/api/videos', {method: 'POST', body: form});
      const freshVideos = await loadVideos();
      const selected = freshVideos.find(item => item.id === uploaded.id);
      if (selected) {
        setVideo(selected); videoRefState.current = selected;
        setScene(null); setRun(null); runRef.current = null;
        setGeometry(blankGeometry()); setPending([]); setDetections([]); setEvents([]); setResult(null);
        setDirty(false); setView('setup'); viewRef.current = 'setup'; setModeState('automatic');
        const freshScenes = await loadScenes(selected, null);
        const freshRuns = await loadRuns(selected);
        if (freshRuns.length) await selectRun(freshRuns[0].id, freshRuns, freshScenes);
      }
      setUploadStatus(`Видео загружено · ${uploaded.name}`);
      flash('Видео загружено. Теперь можно запустить анализ без разметки.', true);
    } finally { setBusy(''); }
  }), [flash, guarded, loadRuns, loadScenes, loadVideos, selectRun]);

  const saveScene = useCallback(() => guarded(async () => {
    if (!video) throw new Error('Сначала выберите видео');
    const name = sceneName.trim();
    if (!name) throw new Error('Введите название зоны');
    setBusy('scene');
    try {
      const payload = {video_id: video.id, name, geometry: {...geometry, mode: 'manual'}};
      const saved = await api(scene ? `/api/scenes/${scene.id}` : '/api/scenes',
        jsonRequest(scene ? 'PUT' : 'POST', payload));
      const fresh = await loadScenes(video, null);
      const selected = fresh.find(item => item.id === saved.id) || saved;
      setScene(selected); setGeometry(cloneGeometry(selected.geometry)); setSceneNameState(selected.name);
      setDirty(false); setModeState('manual');
      flash('Зона сохранена. Можно запустить анализ.', true);
    } finally { setBusy(''); }
  }), [flash, geometry, guarded, loadScenes, scene, sceneName, video]);

  const analyze = useCallback(() => guarded(async () => {
    if (!video) throw new Error('Сначала загрузите видео');
    if (mode === 'manual' && (!scene || dirty)) throw new Error('Сохраните пользовательскую зону перед запуском');
    const payload = mode === 'automatic' ? {video_id: video.id} : {scene_id: scene.id};
    payload.profile = profile; payload.topology = topology;
    if (profile === 'fast') {
      const fps = Number(sampleFps);
      if (!Number.isFinite(fps) || fps < 2 || fps > 12) throw new Error('Частота быстрого режима должна быть от 2 до 12 кадров/с');
      payload.sample_fps = fps;
    }
    setBusy('analyze');
    try {
      const created = await api('/api/runs', jsonRequest('POST', payload));
      const freshRuns = await loadRuns(video);
      await selectRun(created.id, freshRuns, scenes);
      flash('Анализ поставлен в очередь. Статус обновится автоматически.', true);
    } finally { setBusy(''); }
  }), [dirty, flash, guarded, loadRuns, mode, profile, sampleFps, scene, scenes, selectRun, topology, video]);

  const cancelRun = useCallback(() => guarded(async () => {
    if (!runRef.current) return;
    setBusy('cancel');
    try {
      await api(`/api/runs/${runRef.current.id}`, jsonRequest('PATCH', {action: 'cancel'}));
      await loadRuns(); flash('Остановка анализа запрошена', true);
    } finally { setBusy(''); }
  }), [flash, guarded, loadRuns]);

  const refresh = useCallback(() => guarded(async () => {
    setBusy('refresh');
    try { await loadRuns(); await refreshReport(); await loadDetections(true); }
    finally { setBusy(''); }
  }), [guarded, loadDetections, loadRuns, refreshReport]);

  const updateCartogramTopology = useCallback(value => guarded(async () => {
    const selectedRun = runRef.current;
    if (!selectedRun) return;
    setCartogramTopology(value);
    await api(`/api/runs/${selectedRun.id}`, jsonRequest('PATCH', {action: 'set_topology', topology: value}));
    await loadRuns(); await refreshReport();
  }), [guarded, loadRuns, refreshReport]);

  const saveEvent = useCallback(payload => guarded(async () => {
    if (!runRef.current) return false;
    setBusy('event');
    try {
      const id = payload.id;
      await api(`/api/runs/${runRef.current.id}/events`, jsonRequest(id ? 'PATCH' : 'POST', payload));
      await refreshReport(); flash('Событие сохранено', true); setDialogEvent(undefined); return true;
    } finally { setBusy(''); }
  }), [flash, guarded, refreshReport]);

  useEffect(() => { guarded(loadVideos); }, [guarded, loadVideos]);

  useEffect(() => {
    const timer = setInterval(() => {
      const current = runRef.current;
      if (current && activeRunStatuses.includes(current.status)) guarded(async () => {
        const fresh = await loadRuns();
        await refreshReport();
        if (fresh.find(item => item.id === current.id)?.status === 'completed') await loadDetections(true);
      });
    }, 3000);
    return () => clearInterval(timer);
  }, [guarded, loadDetections, loadRuns, refreshReport]);

  return {
    videos, scenes, runs, events, video, scene, run, mode, view, tool, geometry, pending, dirty,
    detections, result, intervalMinutes, topology, cartogramTopology, profile, sampleFps, sceneName,
    lineName, busy, uploadStatus, dialogEvent, videoRef,
    selectVideo: id => guarded(() => selectVideo(id)), selectScene, selectRun: id => guarded(() => selectRun(id)),
    changeMode, setTool, addPoint, finishRoi, undoPoint: () => setPending(current => current.slice(0, -1)),
    removeGeometry, setSceneName, setLineName, uploadVideo, saveScene, analyze, cancelRun, refresh,
    loadDetections, setIntervalMinutes, setTopology, setCartogramTopology: updateCartogramTopology,
    setProfile, setSampleFps, openEvent: event => setDialogEvent(event ?? null), closeEvent: () => setDialogEvent(undefined),
    saveEvent,
  };
}
