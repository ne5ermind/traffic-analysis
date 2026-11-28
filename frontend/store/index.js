import {configureStore, createListenerMiddleware} from '@reduxjs/toolkit';
import {workspaceSlice} from './workspaceSlice.js';
import {sceneEditorSlice} from './sceneEditorSlice.js';

export function createAppStore() {
  const listeners = createListenerMiddleware();
  return configureStore({
    reducer: {
      workspace: workspaceSlice.reducer,
      sceneEditor: sceneEditorSlice.reducer,
    },
    middleware: getDefaultMiddleware => getDefaultMiddleware().prepend(listeners.middleware),
  });
}

export const store = createAppStore();
