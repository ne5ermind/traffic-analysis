import {createSlice} from '@reduxjs/toolkit';
import {blankGeometry} from '../api.js';
import {
  noticeChanged, runSelected, selectResult, selectRunId, selectVideo, videoSelected,
} from './workspaceSlice.js';

const initialState = {
  geometry: blankGeometry(),
  sceneId: '',
  pending: [],
  tool: 'roi',
  editing: false,
  lineName: 'Север',
};

function finishEditing(state) {
  state.pending = [];
  state.editing = false;
}

export const sceneEditorSlice = createSlice({
  name: 'sceneEditor',
  initialState,
  reducers: {
    geometryChanged(state, {payload}) {
      state.geometry = payload;
      state.sceneId = '';
    },
    sceneSelected(state, {payload}) {
      state.sceneId = payload?.id || '';
      if (payload) state.geometry = payload.geometry;
      state.pending = [];
    },
    sceneSaved(state, {payload}) {
      state.sceneId = payload;
    },
    toolSelected(state, {payload}) {
      state.tool = payload;
      state.pending = [];
      state.editing = true;
    },
    editingFinished: finishEditing,
    lineNameChanged(state, {payload}) {
      state.lineName = payload;
    },
    draftPointAdded(state, {payload}) {
      state.pending.push(payload);
      state.sceneId = '';
    },
    draftPointRemoved(state) {
      state.pending.pop();
    },
    lineCompleted(state, {payload}) {
      const {kind, name, points} = payload;
      state.geometry[kind].push({name, points});
      state.sceneId = '';
      finishEditing(state);
    },
  },
  extraReducers: builder => builder
    .addCase(videoSelected, () => initialState)
    .addCase(runSelected, finishEditing),
  selectors: {
    selectGeometry: state => state.geometry,
    selectSceneId: state => state.sceneId,
    selectPending: state => state.pending,
    selectTool: state => state.tool,
    selectEditing: state => state.editing,
    selectLineName: state => state.lineName,
  },
});

export const {
  geometryChanged, sceneSelected, sceneSaved, toolSelected, editingFinished,
  lineNameChanged, draftPointAdded, draftPointRemoved, lineCompleted,
} = sceneEditorSlice.actions;

export const {
  selectGeometry, selectSceneId, selectPending, selectTool, selectEditing, selectLineName,
} = sceneEditorSlice.selectors;

export function selectVisibleGeometry(state) {
  const summary = selectResult(state)?.summary;
  if (summary && !selectEditing(state) && summary.run_id === selectRunId(state)) return summary.geometry;
  return selectGeometry(state);
}

export const addPoint = point => (dispatch, getState) => {
  const state = getState();
  if (!selectVideo(state) || point.some(value => !Number.isFinite(value) || value < 0 || value > 1)) {
    dispatch(noticeChanged('Выберите видео и укажите координаты от 0 до 100%.'));
    return;
  }

  const tool = selectTool(state);
  const pending = selectPending(state);
  if (tool === 'roi' || pending.length === 0) {
    dispatch(draftPointAdded(point));
    return;
  }

  const kind = tool === 'entry' ? 'entries' : 'exits';
  const name = selectLineName(state).trim();
  if (!name || selectGeometry(state)[kind].some(line => line.name === name)) {
    dispatch(noticeChanged('Укажите непустое уникальное имя линии.'));
    return;
  }
  dispatch(lineCompleted({kind, name, points: [...pending, point]}));
};
