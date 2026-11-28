import {addListener} from '@reduxjs/toolkit';
import {api} from '../api.js';
import {
  loadVideos, noticeChanged, refreshRequested, resultsLoaded, runsLoaded, scenesLoaded,
  selectInterval, selectRunId, selectVideoId,
} from './workspaceSlice.js';

const POLL_INTERVAL_MS = 3000;

function scenesNeedRefresh(action, state, previousState) {
  return refreshRequested.match(action) || selectVideoId(state) !== selectVideoId(previousState);
}

const scenesListener = {
  predicate: scenesNeedRefresh,
  async effect(_, listener) {
    listener.cancelActiveListeners();
    const videoId = selectVideoId(listener.getState());
    if (!videoId) return;

    try {
      const scenes = await api(`/api/scenes?video_id=${videoId}`, {signal: listener.signal});
      listener.throwIfCancelled();
      listener.dispatch(scenesLoaded(scenes));
    } catch (error) {
      listener.throwIfCancelled();
      listener.dispatch(noticeChanged(error.message));
    }
  },
};

const analysisListener = {
  predicate: (action, state, previousState) =>
    scenesNeedRefresh(action, state, previousState) ||
    selectRunId(state) !== selectRunId(previousState) ||
    selectInterval(state) !== selectInterval(previousState),
  async effect(_, listener) {
    listener.cancelActiveListeners();
    const state = listener.getState();
    const videoId = selectVideoId(state);
    if (!videoId) return;

    const runId = selectRunId(state);
    const interval = selectInterval(state);
    const {signal, dispatch} = listener;
    while (!signal.aborted) {
      try {
        const runs = await api(`/api/runs?video_id=${videoId}`, {signal});
        listener.throwIfCancelled();
        dispatch(runsLoaded(runs));

        if (runId) {
          listener.throwIfCancelled();
          const result = await api(`/api/runs/${runId}/results?interval=${interval}`, {signal});
          listener.throwIfCancelled();
          dispatch(resultsLoaded(result));
        }
      } catch (error) {
        listener.throwIfCancelled();
        dispatch(noticeChanged(error.message));
      }
      await listener.delay(POLL_INTERVAL_MS);
    }
  },
};

export function startWorkspaceSync(dispatch) {
  const stopScenes = dispatch(addListener(scenesListener));
  const stopAnalysis = dispatch(addListener(analysisListener));
  const archiveRequest = dispatch(loadVideos());
  dispatch(refreshRequested());

  return () => {
    stopScenes({cancelActive: true});
    stopAnalysis({cancelActive: true});
    archiveRequest.abort();
  };
}
