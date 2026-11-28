import {createAsyncThunk, createSlice} from '@reduxjs/toolkit';
import {api} from '../api.js';

export const loadVideos = createAsyncThunk('workspace/loadVideos', (_, {signal}) =>
  api('/api/videos', {signal}),
);

export const workspaceSlice = createSlice({
  name: 'workspace',
  initialState: {
    videos: [],
    videosRequestId: null,
    videoId: '',
    videoSelection: 0,
    scenes: [],
    runs: [],
    runId: '',
    result: null,
    interval: 900,
    revision: 0,
    notice: '',
    pendingOperations: 0,
  },
  reducers: {
    videoSelected(state, {payload}) {
      state.videoId = payload;
      state.videoSelection++;
      state.scenes = [];
      state.runs = [];
      state.runId = '';
      state.result = null;
    },
    runSelected(state, {payload}) {
      if (state.runId === payload) return;
      state.runId = payload;
      state.result = null;
    },
    scenesLoaded(state, {payload}) {
      state.scenes = payload;
    },
    runsLoaded(state, {payload}) {
      state.runs = payload;
    },
    resultsLoaded(state, {payload}) {
      state.result = payload;
    },
    intervalChanged(state, {payload}) {
      state.interval = payload;
    },
    refreshRequested(state) {
      state.revision++;
    },
    noticeChanged(state, {payload}) {
      state.notice = payload;
    },
    operationStarted(state) {
      state.pendingOperations++;
      state.notice = '';
    },
    operationFinished(state) {
      state.pendingOperations--;
    },
  },
  extraReducers: builder => builder
    .addCase(loadVideos.pending, (state, {meta}) => {
      state.videosRequestId = meta.requestId;
    })
    .addCase(loadVideos.fulfilled, (state, {meta, payload}) => {
      if (state.videosRequestId !== meta.requestId) return;
      state.videos = payload;
      state.videosRequestId = null;
    })
    .addCase(loadVideos.rejected, (state, {meta, error}) => {
      if (state.videosRequestId !== meta.requestId) return;
      state.videosRequestId = null;
      if (!meta.aborted) state.notice = error.message;
    }),
  selectors: {
    selectVideos: state => state.videos,
    selectVideo: state => state.videos.find(video => video.id === state.videoId),
    selectVideoId: state => state.videoId,
    selectVideoSelection: state => state.videoSelection,
    selectScenes: state => state.scenes,
    selectRuns: state => state.runs,
    selectRun: state => state.runs.find(run => run.id === state.runId),
    selectRunId: state => state.runId,
    selectResult: state => state.result,
    selectInterval: state => state.interval,
    selectRevision: state => state.revision,
    selectNotice: state => state.notice,
    selectBusy: state => state.pendingOperations > 0,
  },
});

export const {
  videoSelected, runSelected, scenesLoaded, runsLoaded, resultsLoaded,
  intervalChanged, refreshRequested, noticeChanged, operationStarted, operationFinished,
} = workspaceSlice.actions;

export const {
  selectVideos, selectVideo, selectVideoId, selectVideoSelection, selectScenes, selectRuns,
  selectRun, selectRunId, selectResult, selectInterval, selectRevision, selectNotice, selectBusy,
} = workspaceSlice.selectors;
