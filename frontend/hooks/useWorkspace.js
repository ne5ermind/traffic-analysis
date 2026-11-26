import {useCallback, useEffect, useRef, useState} from 'react';
import {api} from '../api';

export function useWorkspace() {
  const [videos, setVideos] = useState([]), [videoId, setVideoId] = useState('');
  const [scenes, setScenes] = useState([]), [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState(''), [result, setResult] = useState(null);
  const [notice, setNotice] = useState(''), [busy, setBusy] = useState(false);
  const [interval, setIntervalSeconds] = useState(900), [revision, setRevision] = useState(0);
  const epoch = useRef(0);
  const refresh = useCallback(() => setRevision(value => value + 1), []);
  const act = useCallback(async action => {
    setBusy(true); setNotice('');
    try { return await action(); } catch (error) { setNotice(error.message); }
    finally { setBusy(false); }
  }, []);
  const loadVideos = useCallback(async () => setVideos(await api('/api/videos')), []);
  useEffect(() => { loadVideos().catch(error => setNotice(error.message)); }, [loadVideos]);
  const selectVideo = id => { epoch.current++; setVideoId(id); setRunId(''); setResult(null); setRuns([]); setScenes([]); };
  const selectRun = id => { setRunId(id); setResult(null); };
  useEffect(() => {
    if (!videoId) return;
    const controller = new AbortController();
    api(`/api/scenes?video_id=${videoId}`, {signal:controller.signal}).then(setScenes).catch(error => {
      if (error.name !== 'AbortError') setNotice(error.message);
    });
    return () => controller.abort();
  }, [videoId, revision]);
  useEffect(() => {
    if (!videoId) return;
    const controller = new AbortController(); let timer;
    const load = async () => {
      try {
        const items = await api(`/api/runs?video_id=${videoId}`, {signal:controller.signal});
        setRuns(items);
        if (runId) {
          const data = await api(`/api/runs/${runId}/results?interval=${interval}`, {signal:controller.signal});
          setResult(data);
        }
      } catch (error) { if (error.name !== 'AbortError') setNotice(error.message); }
      if (!controller.signal.aborted) timer = setTimeout(load, 3000);
    };
    load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [videoId, runId, interval, revision]);
  return {videos, video:videos.find(v => v.id === videoId), videoId, selectVideo,
    scenes, runs, run:runs.find(r => r.id === runId), runId, selectRun, result,
    notice, setNotice, busy, act, loadVideos, refresh, interval, setIntervalSeconds, epoch};
}
