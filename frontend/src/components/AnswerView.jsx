import React from 'react';
import { useApp } from '../store/AppContext';

/**
 * AnswerView — renders the synthesized answer with clickable citation markers.
 *
 * The key UI behavior: [n] markers in the text become clickable elements
 * that highlight the corresponding citation in the CitationPanel.
 */
export default function AnswerView() {
  const { state, setActiveCitation } = useApp();
  const { currentAnswer, streamingText, isStreaming } = state;

  // Nothing to show
  if (!currentAnswer && !streamingText) {
    return (
      <div className="answer-view glass-panel-static">
        <div className="empty-state">
          <div className="icon">🧪</div>
          <p>Ask a question to get a cited answer.<br />
          Every claim will be traced to its source.</p>
        </div>
      </div>
    );
  }

  // Streaming in progress
  if (isStreaming && streamingText) {
    return (
      <div className="answer-view glass-panel-static">
        <h2>✨ Answer</h2>
        <div className="answer-content">
          {streamingText}
          <span className="streaming-cursor" />
        </div>
      </div>
    );
  }

  // Completed answer
  if (currentAnswer) {
    // Check for abstention
    if (currentAnswer.abstained) {
      return (
        <div className="answer-view glass-panel-static">
          <div className="abstention-banner">
            <div className="icon">⚠️</div>
            <div className="message">
              <strong>Cannot Answer</strong>
              {currentAnswer.answer_text.replace(/^ABSTAIN:\s*/i, '')}
            </div>
          </div>
          <div className="answer-metadata">
            <span className="meta-badge">⏱ {Math.round(currentAnswer.latency_ms)}ms</span>
            <span className="meta-badge">ID: {currentAnswer.question_id}</span>
          </div>
        </div>
      );
    }

    // Render answer with clickable citations
    const renderedContent = renderWithCitations(currentAnswer.answer_text, setActiveCitation, state.activeCitation);

    return (
      <div className="answer-view glass-panel-static">
        <h2>✅ Answer</h2>
        <div className="answer-content">{renderedContent}</div>
        <div className="answer-metadata">
          <span className="meta-badge">📎 {currentAnswer.citations?.length || 0} citations</span>
          <span className="meta-badge">⏱ {Math.round(currentAnswer.latency_ms)}ms</span>
          <span className="meta-badge">ID: {currentAnswer.question_id}</span>
        </div>
      </div>
    );
  }

  return null;
}

/**
 * Parse answer text and replace [n] markers with clickable React elements.
 */
function renderWithCitations(text, onClickCitation, activeCitation) {
  if (!text) return null;

  // Split on citation markers [n]
  const parts = text.split(/(\[\d+\])/g);

  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/);
    if (match) {
      const marker = parseInt(match[1]);
      return (
        <span
          key={i}
          className={`citation-marker ${activeCitation === marker ? 'active' : ''}`}
          onClick={() => onClickCitation(marker)}
          title={`Jump to citation [${marker}]`}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onClickCitation(marker)}
        >
          {marker}
        </span>
      );
    }
    // Regular text — render with paragraph breaks
    return <span key={i}>{part}</span>;
  });
}
