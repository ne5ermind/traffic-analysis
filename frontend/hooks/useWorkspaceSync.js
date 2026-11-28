import {useEffect} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {loadAnalysis, loadScenes} from '../store/workspaceActions.js';
import {
  loadVideos, selectInterval, selectRevision, selectRunId, selectVideoId, selectVideoSelection,
} from '../store/workspaceSlice.js';

export function useWorkspaceSync() {
  const dispatch = useDispatch();
  const videoId = useSelector(selectVideoId);
  const videoSelection = useSelector(selectVideoSelection);
  const runId = useSelector(selectRunId);
  const interval = useSelector(selectInterval);
  const revision = useSelector(selectRevision);

  useEffect(() => {
    const request = dispatch(loadVideos());
    return () => request.abort();
  }, [dispatch]);

  useEffect(() => {
    if (!videoId) return;
    const controller = new AbortController();
    dispatch(loadScenes({videoId, videoSelection, revision, signal: controller.signal}));
    return () => controller.abort();
  }, [dispatch, videoId, videoSelection, revision]);

  useEffect(() => {
    if (!videoId) return;
    const controller = new AbortController();
    let timer;

    async function poll() {
      await dispatch(loadAnalysis({
        videoId, videoSelection, runId, interval, revision, signal: controller.signal,
      }));
      if (!controller.signal.aborted) timer = setTimeout(poll, 3000);
    }

    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [dispatch, videoId, videoSelection, runId, interval, revision]);
}
