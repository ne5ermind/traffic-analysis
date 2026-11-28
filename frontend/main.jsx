import React from 'react';
import {createRoot} from 'react-dom/client';
import {Provider} from 'react-redux';
import App from './App';
import {store} from './store/index.js';
class ErrorBoundary extends React.Component {
  state={error:null};
  static getDerivedStateFromError(error){return {error};}
  render(){return this.state.error?<main className="panel"><h1>Не удалось открыть интерфейс</h1><p>Обновите страницу. Сохранённые результаты остаются на сервере.</p><button onClick={()=>location.reload()}>Обновить</button></main>:this.props.children;}
}
createRoot(document.getElementById('root')).render(
  <ErrorBoundary><Provider store={store}><App/></Provider></ErrorBoundary>,
);
