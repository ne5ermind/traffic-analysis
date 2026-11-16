import {Topbar} from './components/Topbar.jsx';
import {Sidebar} from './components/Sidebar.jsx';
import {WorkspaceHeader} from './components/WorkspaceHeader.jsx';
import {VideoPanel} from './components/VideoPanel.jsx';
import {CountingPanel} from './components/CountingPanel.jsx';
import {AnalysisPanel} from './components/AnalysisPanel.jsx';
import {EventDialog} from './components/EventDialog.jsx';
import {useNotice} from './hooks/useNotice.js';
import {useTrafficAnalysis} from './hooks/useTrafficAnalysis.js';

export default function App() {
  const {notice, flash} = useNotice();
  const traffic = useTrafficAnalysis(flash);
  return <>
    <a className="skip-link" href="#mainContent">Перейти к рабочей области</a>
    <Topbar />
    <main className="app-shell" id="mainContent">
      <Sidebar traffic={traffic} />
      <div className="content">
        {notice && <div className={`notice${notice.ok ? ' ok' : ''}`} role="alert" aria-live="assertive">{notice.message}</div>}
        <WorkspaceHeader />
        <VideoPanel traffic={traffic} />
        <CountingPanel traffic={traffic} />
        <AnalysisPanel traffic={traffic} />
      </div>
    </main>
    <EventDialog traffic={traffic} />
  </>;
}
