import React, {useEffect, useState} from 'react';
import {blankGeometry} from './api';
import {useWorkspace} from './hooks/useWorkspace';
import {Sidebar} from './components/Sidebar';
import {VideoPanel} from './components/VideoPanel';
import {ConfigPanel} from './components/ConfigPanel';
import {Results} from './components/Results';
function Workspace({w}) {
  const [geometry,setGeometry]=useState(blankGeometry),[pending,setPending]=useState([]),[sceneId,setSceneId]=useState('');
  const [tool,setTool]=useState('roi'),[editing,setEditing]=useState(false),[lineName,setLineName]=useState('Север');
  useEffect(()=>{setEditing(false);setPending([]);},[w.runId]);
  const onPoint=(point,name=lineName)=>{
    if(!w.video||point.some(value=>!Number.isFinite(value)||value<0||value>1)){w.setNotice('Выберите видео и укажите координаты от 0 до 100%.');return;}
    const points=[...pending,point];setSceneId('');
    if(tool!=='roi'&&points.length===2){
      const kind=tool==='entry'?'entries':'exits';
      if(!name.trim()||geometry[kind].some(line=>line.name===name.trim())){w.setNotice('Укажите непустое уникальное имя линии.');return;}
      setGeometry({...geometry,[kind]:[...geometry[kind],{name:name.trim(),points}]});setPending([]);setEditing(false);
    } else setPending(points);
  };
  const visibleGeometry=!editing&&w.result?.summary?.run_id===w.runId?w.result.summary.geometry:geometry;
  return <div className="content"><div className="workspace-head"><h1>Монитор движения</h1></div>
    {w.notice&&<div id="notice" className="notice" role="alert">{w.notice}<button aria-label="Закрыть уведомление" onClick={()=>w.setNotice('')}>×</button></div>}
    <VideoPanel video={w.video} runId={editing?'':w.runId} geometry={visibleGeometry} pending={pending} onPoint={onPoint} editing={editing}/>
    <ConfigPanel workspace={w} {...{geometry,setGeometry,sceneId,setSceneId,pending,setPending,tool,setTool,editing,setEditing,onPoint,lineName,setLineName}}/>
    <Results key={w.runId} workspace={w}/>
  </div>;
}
export default function App() {
  const w=useWorkspace();
  return <><a className="skip-link" href="#mainContent">Перейти к рабочей области</a><header className="topbar"><div className="brand"><strong>InnovaTransport</strong><span>Анализ транспортных потоков</span></div><span className="system-badge">Локальная обработка</span></header><main className="app-shell" id="mainContent"><Sidebar workspace={w}/><Workspace key={w.videoId} w={w}/></main></>;
}
