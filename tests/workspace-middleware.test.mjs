import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';
import {test} from 'node:test';
import {createAppStore} from '../frontend/store/index.js';
import {openVideo} from '../frontend/store/workspaceActions.js';
import {startWorkspaceSync} from '../frontend/store/workspaceMiddleware.js';
import {
  intervalChanged, refreshRequested, runSelected, selectNotice, selectResult, selectRuns, selectScenes,
} from '../frontend/store/workspaceSlice.js';

function mockRequests(t) {
  const requests = [];
  const fetch = t.mock.method(globalThis, 'fetch', (url, {signal}) => new Promise(resolve => {
    requests.push({
      url,
      signal,
      respond: (data, ok = true) => resolve({ok, json: async () => data}),
    });
  }));
  return {
    take(url) {
      const index = requests.findIndex(request => request.url === url);
      assert.notEqual(index, -1, `Expected a request for ${url}`);
      return requests.splice(index, 1)[0];
    },
    callCount: () => fetch.mock.callCount(),
  };
}

test('selection and interval changes cancel requests and discard late responses', async t => {
  const requests = mockRequests(t);
  const {dispatch, getState} = createAppStore();
  t.after(startWorkspaceSync(dispatch));
  requests.take('/api/videos').respond([{id:'a'}, {id:'b'}]);

  dispatch(openVideo('a'));
  const oldScene = requests.take('/api/scenes?video_id=a');
  const initialRuns = requests.take('/api/runs?video_id=a');
  dispatch(runSelected('run-a'));
  assert.equal(initialRuns.signal.aborted, true);
  initialRuns.respond([]);
  requests.take('/api/runs?video_id=a').respond([{id:'run-a'}]);
  await setImmediate();
  const oldResult = requests.take('/api/runs/run-a/results?interval=900');

  dispatch(openVideo('b'));
  assert.equal(oldScene.signal.aborted, true);
  assert.equal(oldResult.signal.aborted, true);
  requests.take('/api/scenes?video_id=b').respond([{id:'scene-b'}]);
  requests.take('/api/runs?video_id=b').respond([]);
  dispatch(runSelected('run-b'));
  requests.take('/api/runs?video_id=b').respond([{id:'run-b'}]);
  await setImmediate();
  const oldInterval = requests.take('/api/runs/run-b/results?interval=900');

  dispatch(intervalChanged(300));
  assert.equal(oldInterval.signal.aborted, true);
  requests.take('/api/runs?video_id=b').respond([{id:'run-b'}]);
  await setImmediate();
  const result = {summary:{run_id:'run-b'}, interval:300};
  requests.take('/api/runs/run-b/results?interval=300').respond(result);
  oldScene.respond([{id:'scene-a'}]);
  oldResult.respond({summary:{run_id:'run-a'}});
  oldInterval.respond({detail:'Error from the previous interval'}, false);
  await setImmediate();

  assert.deepEqual(selectScenes(getState()), [{id:'scene-b'}]);
  assert.deepEqual(selectRuns(getState()), [{id:'run-b'}]);
  assert.deepEqual(selectResult(getState()), result);
  assert.equal(selectNotice(getState()), '');
});

test('polling retries after an error and cleanup stops requests and timers', async t => {
  t.mock.timers.enable({apis:['setTimeout']});
  const requests = mockRequests(t);
  const {dispatch, getState} = createAppStore();
  const stop = startWorkspaceSync(dispatch);
  t.after(stop);
  const archive = requests.take('/api/videos');
  dispatch(openVideo('a'));
  requests.take('/api/scenes?video_id=a').respond([]);
  requests.take('/api/runs?video_id=a').respond({detail:'Temporarily unavailable'}, false);
  await setImmediate();
  assert.equal(selectNotice(getState()), 'Temporarily unavailable');

  const requestsBeforeRetry = requests.callCount();
  t.mock.timers.tick(2999);
  await setImmediate();
  assert.equal(requests.callCount(), requestsBeforeRetry);
  t.mock.timers.tick(1);
  await setImmediate();
  requests.take('/api/runs?video_id=a').respond([{id:'run-a'}]);
  await setImmediate();
  assert.deepEqual(selectRuns(getState()), [{id:'run-a'}]);

  dispatch(refreshRequested());
  const scenes = requests.take('/api/scenes?video_id=a');
  const runs = requests.take('/api/runs?video_id=a');
  stop();
  assert.equal(archive.signal.aborted, true);
  assert.equal(scenes.signal.aborted, true);
  assert.equal(runs.signal.aborted, true);
  archive.respond([]);
  scenes.respond([]);
  runs.respond([]);
  const requestsAfterStop = requests.callCount();
  dispatch(refreshRequested());
  t.mock.timers.tick(9000);
  await setImmediate();
  assert.equal(requests.callCount(), requestsAfterStop);
  assert.deepEqual(selectRuns(getState()), [{id:'run-a'}]);
});
