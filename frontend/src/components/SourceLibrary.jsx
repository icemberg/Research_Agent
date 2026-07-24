import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../store/AppContext';

export default function SourceLibrary() {
  const { state, uploadFiles, fetchDocuments } = useApp();
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) uploadFiles(files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) uploadFiles(files);
  };

  return (
    <div className="source-library glass-panel-static">
      <h2>📚 Source Library</h2>

      <div
        className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="icon">📄</div>
        <p>Drop files here or click to upload</p>
        <p className="formats">PDF, DOCX, TXT, MD, HTML, CSV</p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.txt,.md,.html,.htm,.csv"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* Upload Progress */}
      {state.uploadProgress.length > 0 && (
        <div className="upload-progress">
          {state.uploadProgress.map((p, i) => (
            <div key={i} className="upload-progress-item">
              <span className="filename">{p.filename}</span>
              <span className={`status ${p.status}`}>
                {p.status === 'uploading' && '⏳ Uploading...'}
                {p.status === 'success' && `✓ ${p.chunks} chunks`}
                {p.status === 'error' && '✗ Error'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Document List */}
      {state.documents.length > 0 ? (
        <ul className="doc-list">
          {state.documents.map((doc, i) => (
            <li key={i} className="doc-item">
              <span className="doc-name" title={doc.name}>{doc.name}</span>
              <span className="doc-chunks">{doc.chunk_count} chunks</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-state">
          <p>No documents yet.<br />Upload files to build your corpus.</p>
        </div>
      )}
    </div>
  );
}
