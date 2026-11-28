import {
  noticeChanged, operationFinished, operationStarted, runSelected, selectRunId, selectVideoId,
  videoSelected,
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
