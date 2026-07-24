import React, { useState, useRef } from 'react';
import { useApp } from '../store/AppContext';

export default function AskPanel() {
  const { state, askQuestion, toggleWebSearch } = useApp();
  const [question, setQuestion] = useState('');
  const inputRef = useRef(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!question.trim() || state.isLoading || state.isStreaming) return;
    askQuestion(question.trim());
    setQuestion('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const isDisabled = state.isLoading || state.isStreaming || !question.trim();

  return (
    <div className="ask-panel glass-panel-static">
      <h2>🔍 Ask a Research Question</h2>
      <form onSubmit={handleSubmit}>
        <div className="question-input-wrapper">
          <textarea
            ref={inputRef}
            className="question-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="What would you like to know? Every claim will be cited..."
            rows={2}
            disabled={state.isLoading || state.isStreaming}
          />
        </div>
        <div className="ask-controls">
          <label className="web-toggle">
            <input
              type="checkbox"
              checked={state.webSearchEnabled}
              onChange={toggleWebSearch}
            />
            <span>🌐 Web search</span>
          </label>
          <div style={{ flex: 1 }} />
          <button
            type="submit"
            className={`ask-btn ${state.isLoading || state.isStreaming ? 'loading' : ''}`}
            disabled={isDisabled}
          >
            {state.isLoading || state.isStreaming ? 'Thinking...' : 'Ask →'}
          </button>
        </div>
      </form>

      {/* Status */}
      {state.statusMessage && (
        <div className="status-indicator">
          <div className="dot" />
          <span>{state.statusMessage}</span>
        </div>
      )}
    </div>
  );
}
