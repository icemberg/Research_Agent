import React from 'react';
import SourceLibrary from './components/SourceLibrary';
import AskPanel from './components/AskPanel';
import AnswerView from './components/AnswerView';
import CitationPanel from './components/CitationPanel';
import HistoryView from './components/HistoryView';

export default function App() {
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div>
          <h1>Research Agent</h1>
          <span className="subtitle">Every claim cited. Every source traceable.</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="meta-badge">🤖 RAG + Citations</span>
        </div>
      </header>

      {/* Left sidebar: Sources + History */}
      <div className="sidebar-left">
        <SourceLibrary />
        <HistoryView />
      </div>

      {/* Main area: Ask + Answer */}
      <div className="main-area">
        <AskPanel />
        <AnswerView />
      </div>

      {/* Right sidebar: Citations */}
      <div className="sidebar-right">
        <CitationPanel />
      </div>
    </div>
  );
}
