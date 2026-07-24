import React, { useEffect, useRef } from 'react';
import { useApp } from '../store/AppContext';

/**
 * CitationPanel — side panel showing all citations with source info.
 * Clicking a citation marker in AnswerView highlights the card here.
 */
export default function CitationPanel() {
  const { state, setActiveCitation } = useApp();
  const { currentAnswer, activeCitation } = state;
  const activeRef = useRef(null);

  // Auto-scroll to active citation
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [activeCitation]);

  const citations = currentAnswer?.citations || [];

  if (!currentAnswer || citations.length === 0) {
    return (
      <div className="citation-panel glass-panel-static">
        <h2>📌 Citations</h2>
        <div className="empty-state">
          <div className="icon">📋</div>
          <p>Citations will appear here<br />when you ask a question.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="citation-panel glass-panel-static">
      <h2>📌 Citations ({citations.length})</h2>
      <div className="citation-list">
        {citations.map((citation, i) => (
          <div
            key={i}
            ref={activeCitation === citation.marker ? activeRef : null}
            className={`citation-card ${activeCitation === citation.marker ? 'highlighted' : ''}`}
            onClick={() => setActiveCitation(
              activeCitation === citation.marker ? null : citation.marker
            )}
          >
            <span className="marker-badge">[{citation.marker}]</span>
            <div className="source">{citation.source}</div>
            <div className="location">{citation.location}</div>
            <div className="snippet">"{citation.snippet}"</div>
          </div>
        ))}
      </div>
    </div>
  );
}
