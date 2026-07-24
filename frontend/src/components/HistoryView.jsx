import React, { useEffect } from 'react';
import { useApp } from '../store/AppContext';

export default function HistoryView() {
  const { state, fetchHistory, loadHistoryItem } = useApp();

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  // Refresh history when a new answer comes in
  useEffect(() => {
    if (state.currentAnswer) {
      fetchHistory();
    }
  }, [state.currentAnswer, fetchHistory]);

  if (state.history.length === 0) {
    return (
      <div className="history-view glass-panel-static">
        <h2>📜 History</h2>
        <div className="empty-state">
          <p>Past questions will appear here.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="history-view glass-panel-static">
      <h2>📜 History ({state.history.length})</h2>
      {state.history.map((item, i) => (
        <div
          key={i}
          className="history-item"
          onClick={() => loadHistoryItem(item)}
        >
          <div className="question">
            {item.abstained ? '⚠️ ' : '✅ '}
            {item.question}
          </div>
          <div className="preview">
            {item.answer_text?.substring(0, 100)}...
          </div>
          <div className="meta">
            {item.citations?.length || 0} citations · {Math.round(item.latency_ms)}ms
          </div>
        </div>
      ))}
    </div>
  );
}
