import React, {useState} from 'react';
import {api, jsonRequest} from '../api';
export function ConfigPanel({workspace:w, geometry, setGeometry, sceneId, setSceneId, pending, setPending, tool, setTool, editing, setEditing, onPoint, lineName, setLineName}) {
  const [name,setName]=useState('Моя зона');
  const [x,setX]=useState(50),[y,setY]=useState(50),[profile,setProfile]=useState('fast');
  const [fps,setFps]=useState(6),[lighting,setLighting]=useState('auto'),[nightModel,setNightModel]=useState('');
  const [topology,setTopology]=useState('auto');
  const update = next => {setGeometry(next);setSceneId('');};
  const mode = value => {update({...geometry,mode:value,entries:[],exits:[]});setPending([]);setEditing(false);};
  const finish = () => {
    if(pending.length < 3) {w.setNotice('Для области нужны минимум три точки.');return;}
    update({...geometry,roi:pending});setPending([]);setEditing(false);
  };
  const save = async () => {
    if (!w.video) throw Error('Сначала выберите видео.');
    if (pending.length) throw Error('Завершите текущую линию или область.');
    const scene=await api('/api/scenes',jsonRequest('POST',{video_id:w.videoId,name,geometry}));
    setSceneId(scene.id);w.refresh();w.setNotice('Зона сохранена.');return scene;
  };
  const analyze=()=>w.act(async()=>{
    if(pending.length) throw Error('Завершите разметку перед анализом.');
    if(!Number.isFinite(Number(fps)) || Number(fps)<2 || Number(fps)>12) throw Error('Укажите частоту от 2 до 12 кадров/с.');
    let selected=sceneId;
    if(!selected && (geometry.mode==='manual'||geometry.roi.length)) selected=(await save()).id;
    const payload={...(selected?{scene_id:selected}:{video_id:w.videoId}),profile,sample_fps:Number(fps),lighting,topology};
    if(nightModel.trim()) payload.night_model=`data/models/${nightModel.trim()}`;
    const run=await api('/api/runs',jsonRequest('POST',payload));w.selectRun(run.id);w.refresh();setEditing(false);
  });
  return <section className="panel zone-panel" aria-labelledby="zoneHeading"><h2 id="zoneHeading">Конфигурация</h2>
    <div className="mode-switch"><button id="autoMode" aria-pressed={geometry.mode==='automatic'} className={geometry.mode==='automatic'?'selected':''} onClick={()=>mode('automatic')}>Автоматически</button><button id="manualMode" aria-pressed={geometry.mode==='manual'} className={geometry.mode==='manual'?'selected':''} onClick={()=>mode('manual')}>По зоне</button></div>
    <p className="mode-info">{geometry.mode==='automatic'?'Каждый устойчивый трек учитывается один раз внутри области.':'Подсчёт между линиями въезда и выезда; события доступны для проверки.'}</p>
    <label>Сохранённая зона<select id="sceneSelect" value={sceneId} onChange={e=>{const scene=w.scenes.find(s=>s.id===e.target.value);setSceneId(scene?.id||'');if(scene){setGeometry(scene.geometry);setName(scene.name);}setPending([]);}}><option value="">Новая зона</option>{w.scenes.map(scene=><option key={scene.id} value={scene.id}>{scene.name}</option>)}</select></label>
    <div className="toolbar" role="group" aria-label="Инструменты разметки">
      {geometry.mode==='manual'&&<><button data-tool="entry" aria-pressed={editing&&tool==='entry'} onClick={()=>{setTool('entry');setEditing(true);setPending([]);}}>Линия въезда</button><button data-tool="exit" aria-pressed={editing&&tool==='exit'} onClick={()=>{setTool('exit');setEditing(true);setPending([]);}}>Линия выезда</button></>}
      <button id="startAutoRoi" onClick={()=>{setTool('roi');setEditing(true);setPending([]);}}>Нарисовать область</button>
      {editing&&tool==='roi'&&<button id="finishRoi" onClick={finish}>Сохранить область</button>}
      <button onClick={()=>{update({...geometry,roi:[]});setPending([]);setEditing(false);}}>Весь кадр</button>
    </div>
    {editing&&<div className="coordinate-editor">
      {tool!=='roi'&&<label>Имя линии<input id="lineName" value={lineName} onChange={e=>setLineName(e.target.value)}/></label>}
      <div className="formrow"><label>X, %<input id="pointX" type="number" min="0" max="100" value={x} onChange={e=>setX(e.target.value)}/></label><label>Y, %<input id="pointY" type="number" min="0" max="100" value={y} onChange={e=>setY(e.target.value)}/></label></div>
      <button id="addPoint" onClick={()=>onPoint([Number(x)/100,Number(y)/100],lineName)}>Добавить точку</button>
      <button onClick={()=>setPending(pending.slice(0,-1))}>Отменить точку</button><button onClick={()=>{setEditing(false);setPending([]);}}>Закончить разметку</button>
    </div>}
    <div className="chips">{geometry.roi.length>0&&<span>Область: {geometry.roi.length} точек</span>}{['entries','exits'].flatMap(kind=>geometry[kind].map((line,index)=><button key={`${kind}-${index}`} title="Удалить линию" onClick={()=>update({...geometry,[kind]:geometry[kind].filter((_,i)=>i!==index)})}>{kind==='entries'?'Въезд':'Выезд'}: {line.name} ×</button>))}</div>
    <label>Название зоны<input id="sceneName" value={name} onChange={e=>setName(e.target.value)}/></label><button id="saveScene" disabled={!w.video||w.busy} onClick={()=>w.act(save)}>Сохранить зону</button>
    <div className="settings formrow"><h3>Обработка</h3>
      <label>Режим обработки<select id="profile" value={profile} onChange={e=>setProfile(e.target.value)}><option value="fast">Быстрый · YOLO11s</option><option value="ensemble">Ансамбль · две модели</option></select></label>
      {profile==='fast'&&<label id="sampleFpsControl">Кадров в секунду<input id="sampleFps" type="number" min="2" max="12" value={fps} onChange={e=>setFps(e.target.value)}/></label>}
      <label>Освещение<select id="lighting" value={lighting} onChange={e=>setLighting(e.target.value)}><option value="auto">Определять автоматически</option><option value="day">День</option><option value="night">Ночь / тёмное видео</option></select></label>
      {lighting!=='day'&&<><p className="mode-info">Тёмные кадры проходят коррекцию яркости. Отдельные веса ночного детектора можно указать ниже; без них используется обычная модель.</p><label>Ночная модель, необязательно<input id="nightModel" value={nightModel} placeholder="yolo11s-night.pt" onChange={e=>setNightModel(e.target.value)}/></label></>}
      <label>Схема перекрёстка<select value={topology} onChange={e=>setTopology(e.target.value)}><option value="auto">Определять автоматически</option><option value="three_way">Три луча</option><option value="four_way">Четыре луча</option></select></label>
      <p className="mode-info">Кластеры формируются из похожих направленных траекторий. Редкие и неоднозначные движения остаются отдельно.</p>
      <button id="analyze" className="primary action" disabled={!w.video||w.video.available===false||w.busy} onClick={analyze}>{w.busy?'Подождите…':'Запустить анализ'}</button>
    </div>
  </section>;
}
