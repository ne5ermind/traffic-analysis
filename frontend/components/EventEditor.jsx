import React, {useEffect, useRef, useState} from 'react';
import {useDispatch, useSelector} from 'react-redux';
import {api, categories, jsonRequest, statuses} from '../api';
import {runWorkspaceAction} from '../store/workspaceActions.js';
import {refreshRequested, selectBusy, selectRunId, selectVideo} from '../store/workspaceSlice.js';

export function EventEditor({event, geometry, onClose}) {
  const dispatch = useDispatch();
  const runId = useSelector(selectRunId);
  const video = useSelector(selectVideo);
  const busy = useSelector(selectBusy);
  const dialog=useRef(null);
  const [form,setForm]=useState(()=>({category:'car',time_s:0,status:'confirmed',from_direction:geometry.mode==='automatic'?'В кадре':geometry.entries[0]?.name||'',to_direction:geometry.mode==='automatic'?'В кадре':geometry.exits[0]?.name||'',reason:'',...event}));
  const [error,setError]=useState('');
  useEffect(()=>{dialog.current.showModal();},[]);
  const field=(key,value)=>setForm({...form,[key]:value});
  const save = async e => {
    e.preventDefault();
    setError('');
    await dispatch(runWorkspaceAction(async () => {
      try {
        await api(`/api/runs/${runId}/events`, jsonRequest(event?.id ? 'PATCH' : 'POST', form));
        dispatch(refreshRequested());
        onClose();
      } catch (error) {
        setError(error.message);
        throw error;
      }
    }));
  };
  return <dialog id="eventDialog" ref={dialog} onCancel={onClose} aria-labelledby="eventTitle"><form id="eventForm" onSubmit={save}>
    <h2 id="eventTitle">{event?.id?'Проверить событие':'Добавить пропущенный объект'}</h2>
    {error&&<p role="alert">{error}</p>}
    <div className="grid2"><label>Время, сек<input id="eventTime" type="number" min="0" max={video?.duration} step="0.01" required value={form.time_s} onChange={e=>field('time_s',Number(e.target.value))}/></label>
      <label>Категория<select id="eventCategory" value={form.category} onChange={e=>field('category',e.target.value)}>{Object.entries(categories).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
      {['from_direction','to_direction'].map((key,i)=><label key={key}>{i?'Куда':'Откуда'}<select value={form[key]} onChange={e=>field(key,e.target.value)}>{(geometry.mode==='automatic'?['В кадре']:geometry[i?'exits':'entries'].map(line=>line.name)).map(name=><option key={name}>{name}</option>)}</select></label>)}
      <label>Статус<select id="eventStatus" value={form.status} onChange={e=>field('status',e.target.value)}>{['confirmed','review','auto_accept','discarded'].map(value=><option key={value} value={value}>{statuses[value]}</option>)}</select></label>
      <label>Причина правки<input value={form.reason} onChange={e=>field('reason',e.target.value)}/></label></div>
    <menu><button type="button" onClick={onClose}>Отмена</button><button id="eventSave" className="primary" disabled={busy}>Сохранить</button></menu>
  </form></dialog>;
}
