import React, {useState} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {api, jsonRequest} from '../api';
import {
  addPoint, draftPointRemoved, editingFinished, geometryChanged, lineNameChanged, sceneSaved,
  sceneSelected, selectEditing, selectGeometry, selectLineName, selectPending, selectSceneId,
  selectTool, toolSelected,
} from '../store/sceneEditorSlice.js';
import {runWorkspaceAction} from '../store/workspaceActions.js';
import {
  noticeChanged, refreshRequested, runSelected, selectBusy, selectScenes, selectVideo,
  selectVideoSelection,
} from '../store/workspaceSlice.js';

export function ConfigPanel() {
  const dispatch = useDispatch();
  const video = useSelector(selectVideo);
  const scenes = useSelector(selectScenes);
  const busy = useSelector(selectBusy);
  const geometry = useSelector(selectGeometry);
  const sceneId = useSelector(selectSceneId);
  const pending = useSelector(selectPending);
  const tool = useSelector(selectTool);
  const editing = useSelector(selectEditing);
  const lineName = useSelector(selectLineName);
  const [name,setName]=useState('Моя зона');
  const [x,setX]=useState(50),[y,setY]=useState(50),[profile,setProfile]=useState('fast');
  const [fps,setFps]=useState(6),[lighting,setLighting]=useState('auto'),[nightModel,setNightModel]=useState('');
  const [topology,setTopology]=useState('auto');
  const update = next => dispatch(geometryChanged(next));
  const finishEditing = () => dispatch(editingFinished());
  const mode = value => {
    update({...geometry,mode:value,entries:[],exits:[]});
    finishEditing();
  };
  const finish = () => {
    if (pending.length < 3) {
      dispatch(noticeChanged('Для области нужны минимум три точки.'));
      return;
    }
    update({...geometry,roi:pending});
    finishEditing();
  };

  const save = async (dispatch, getState) => {
    if (!video) throw Error('Сначала выберите видео.');
    if (pending.length) throw Error('Завершите текущую линию или область.');
    const selection = selectVideoSelection(getState());
    const scene = await api('/api/scenes', jsonRequest('POST', {video_id:video.id,name,geometry}));
    const state = getState();
    if (selectVideoSelection(state) === selection) {
      if (selectGeometry(state) === geometry && selectPending(state) === pending &&
          selectSceneId(state) === sceneId) {
        dispatch(sceneSaved(scene.id));
      }
      dispatch(refreshRequested());
      dispatch(noticeChanged('Зона сохранена.'));
    }
    return scene;
  };
  const analyze = () => dispatch(runWorkspaceAction(async (dispatch, getState) => {
    const selection = selectVideoSelection(getState());
    if(pending.length) throw Error('Завершите разметку перед анализом.');
    if(!Number.isFinite(Number(fps)) || Number(fps)<2 || Number(fps)>12) throw Error('Укажите частоту от 2 до 12 кадров/с.');
    let selected=sceneId;
    if(!selected && (geometry.mode==='manual'||geometry.roi.length)) selected=(await save(dispatch, getState)).id;
    const payload={...(selected?{scene_id:selected}:{video_id:video.id}),profile,sample_fps:Number(fps),lighting,topology};
    if(nightModel.trim()) payload.night_model=`data/models/${nightModel.trim()}`;
    const run = await api('/api/runs', jsonRequest('POST', payload));
    if (selectVideoSelection(getState()) === selection) {
      dispatch(runSelected(run.id));
      dispatch(refreshRequested());
    }
  }));
  const openScene = id => {
    const scene = scenes.find(scene => scene.id === id);
    dispatch(sceneSelected(scene));
    if (scene) setName(scene.name);
  };

  return <section className="panel zone-panel" aria-labelledby="zoneHeading"><h2 id="zoneHeading">Конфигурация</h2>
    <div className="mode-switch"><button id="autoMode" aria-pressed={geometry.mode==='automatic'} className={geometry.mode==='automatic'?'selected':''} onClick={()=>mode('automatic')}>Автоматически</button><button id="manualMode" aria-pressed={geometry.mode==='manual'} className={geometry.mode==='manual'?'selected':''} onClick={()=>mode('manual')}>По зоне</button></div>
    <p className="mode-info">{geometry.mode==='automatic'?'Каждый устойчивый трек учитывается один раз внутри области.':'Подсчёт между линиями въезда и выезда; события доступны для проверки.'}</p>
    <label>Сохранённая зона<select id="sceneSelect" value={sceneId} onChange={e=>openScene(e.target.value)}><option value="">Новая зона</option>{scenes.map(scene=><option key={scene.id} value={scene.id}>{scene.name}</option>)}</select></label>
    <div className="toolbar" role="group" aria-label="Инструменты разметки">
      {geometry.mode==='manual'&&<><button data-tool="entry" aria-pressed={editing&&tool==='entry'} onClick={()=>dispatch(toolSelected('entry'))}>Линия въезда</button><button data-tool="exit" aria-pressed={editing&&tool==='exit'} onClick={()=>dispatch(toolSelected('exit'))}>Линия выезда</button></>}
      <button id="startAutoRoi" onClick={()=>dispatch(toolSelected('roi'))}>Нарисовать область</button>
      {editing&&tool==='roi'&&<button id="finishRoi" onClick={finish}>Сохранить область</button>}
      <button onClick={()=>{update({...geometry,roi:[]});finishEditing();}}>Весь кадр</button>
    </div>
    {editing&&<div className="coordinate-editor">
      {tool!=='roi'&&<label>Имя линии<input id="lineName" value={lineName} onChange={e=>dispatch(lineNameChanged(e.target.value))}/></label>}
      <div className="formrow"><label>X, %<input id="pointX" type="number" min="0" max="100" value={x} onChange={e=>setX(e.target.value)}/></label><label>Y, %<input id="pointY" type="number" min="0" max="100" value={y} onChange={e=>setY(e.target.value)}/></label></div>
      <button id="addPoint" onClick={()=>dispatch(addPoint([Number(x)/100,Number(y)/100]))}>Добавить точку</button>
      <button onClick={()=>dispatch(draftPointRemoved())}>Отменить точку</button><button onClick={finishEditing}>Закончить разметку</button>
    </div>}
    <div className="chips">{geometry.roi.length>0&&<span>Область: {geometry.roi.length} точек</span>}{['entries','exits'].flatMap(kind=>geometry[kind].map((line,index)=><button key={`${kind}-${index}`} title="Удалить линию" onClick={()=>update({...geometry,[kind]:geometry[kind].filter((_,i)=>i!==index)})}>{kind==='entries'?'Въезд':'Выезд'}: {line.name} ×</button>))}</div>
    <label>Название зоны<input id="sceneName" value={name} onChange={e=>setName(e.target.value)}/></label><button id="saveScene" disabled={!video||busy} onClick={()=>dispatch(runWorkspaceAction(save))}>Сохранить зону</button>
    <div className="settings formrow"><h3>Обработка</h3>
      <label>Режим обработки<select id="profile" value={profile} onChange={e=>setProfile(e.target.value)}><option value="fast">Быстрый · YOLO11s</option><option value="ensemble">Ансамбль · две модели</option></select></label>
      {profile==='fast'&&<label id="sampleFpsControl">Кадров в секунду<input id="sampleFps" type="number" min="2" max="12" value={fps} onChange={e=>setFps(e.target.value)}/></label>}
      <label>Освещение<select id="lighting" value={lighting} onChange={e=>setLighting(e.target.value)}><option value="auto">Определять автоматически</option><option value="day">День</option><option value="night">Ночь / тёмное видео</option></select></label>
      {lighting!=='day'&&<><p className="mode-info">Тёмные кадры проходят коррекцию яркости. Отдельные веса ночного детектора можно указать ниже; без них используется обычная модель.</p><label>Ночная модель, необязательно<input id="nightModel" value={nightModel} placeholder="yolo11s-night.pt" onChange={e=>setNightModel(e.target.value)}/></label></>}
      <label>Схема перекрёстка<select value={topology} onChange={e=>setTopology(e.target.value)}><option value="auto">Определять автоматически</option><option value="three_way">Три луча</option><option value="four_way">Четыре луча</option></select></label>
      <p className="mode-info">Кластеры формируются из похожих направленных траекторий. Редкие и неоднозначные движения остаются отдельно.</p>
      <button id="analyze" className="primary action" disabled={!video||video.available===false||busy} onClick={analyze}>{busy?'Подождите…':'Запустить анализ'}</button>
    </div>
  </section>;
}
