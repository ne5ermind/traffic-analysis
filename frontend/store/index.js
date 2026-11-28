import {configureStore} from '@reduxjs/toolkit';
import {workspaceSlice} from './workspaceSlice.js';
import {sceneEditorSlice} from './sceneEditorSlice.js';

export const store = configureStore({
  reducer: {
    workspace: workspaceSlice.reducer,
    sceneEditor: sceneEditorSlice.reducer,
  },
});
