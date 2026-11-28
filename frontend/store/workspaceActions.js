import {api} from '../api.js';
import {
  noticeChanged, operationFinished, operationStarted, resultsLoaded, runSelected, runsLoaded, scenesLoaded,
  selectInterval, selectRevision, selectRunId, selectVideoId, selectVideoSelection, videoSelected,
} from './workspaceSlice.js';

export const openVideo = videoId => (dispatch, getState) => {
  const state = getState();
  if (selectVideoId(state) !== videoId) dispatch(videoSelected(videoId));
  else if (selectRunId(state)) dispatch(runSelected(''));
};

export const runWorkspaceAction = action => async (dispatch, getState) => {
  dispatch(operationStarted());
  try {
    return await action(dispatch, getState);
  } catch (error) {
    dispatch(noticeChanged(error.message));
  } finally {
    dispatch(operationFinished());
  }
};

export const loadScenes = ({videoId, videoSelection, revision, signal}) => async (dispatch, getState) => {
  const isCurrent = () => {
    const state = getState();
    return !signal.aborted && selectVideoSelection(state) === videoSelection &&
      selectRevision(state) === revision;
  };
  try {
    const scenes = await api(`/api/scenes?video_id=${videoId}`, {signal});
    if (isCurrent()) dispatch(scenesLoaded(scenes));
  } catch (error) {
    if (isCurrent()) dispatch(noticeChanged(error.message));
  }
};

export const loadAnalysis = ({videoId, videoSelection, runId, interval, revision, signal}) =>
  async (dispatch, getState) => {
    const isCurrent = () => {
      const state = getState();
      return !signal.aborted && selectVideoSelection(state) === videoSelection &&
        selectRevision(state) === revision && selectRunId(state) === runId &&
        selectInterval(state) === interval;
    };
    try {
      const runs = await api(`/api/runs?video_id=${videoId}`, {signal});
      if (!isCurrent()) return;
      dispatch(runsLoaded(runs));
      if (runId) {
        const result = await api(`/api/runs/${runId}/results?interval=${interval}`, {signal});
        if (isCurrent()) dispatch(resultsLoaded(result));
      }
    } catch (error) {
      if (isCurrent()) dispatch(noticeChanged(error.message));
    }
  };
