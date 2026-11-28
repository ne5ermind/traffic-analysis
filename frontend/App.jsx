import React, {useEffect} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {startWorkspaceSync} from './store/workspaceMiddleware.js';
import {noticeChanged, selectNotice, selectRunId, selectVideoId} from './store/workspaceSlice.js';
import {Sidebar} from './components/Sidebar';
import {VideoPanel} from './components/VideoPanel';
import {ConfigPanel} from './components/ConfigPanel';
import {Results} from './components/Results';
function Workspace() {
  const dispatch = useDispatch();
  const notice = useSelector(selectNotice);
  const runId = useSelector(selectRunId);
  return <div className="content"><div className="workspace-head"><h1>Монитор движения</h1></div>
    {notice&&<div id="notice" className="notice" role="alert">{notice}<button aria-label="Закрыть уведомление" onClick={()=>dispatch(noticeChanged(''))}>×</button></div>}
    <VideoPanel/>
    <ConfigPanel/>
    <Results key={runId}/>
  </div>;
}
export default function App() {
  const dispatch = useDispatch();
  const videoId = useSelector(selectVideoId);
  useEffect(() => startWorkspaceSync(dispatch), [dispatch]);
  return <><a className="skip-link" href="#mainContent">Перейти к рабочей области</a><header className="topbar"><div className="brand"><strong>InnovaTransport</strong><span>Анализ транспортных потоков</span></div><span className="system-badge">Локальная обработка</span></header><main className="app-shell" id="mainContent"><Sidebar/><Workspace key={videoId}/></main></>;
}
