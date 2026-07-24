import React, { createContext, useContext, useReducer, useCallback } from 'react';

const AppContext = createContext(null);

const initialState = {
  // Documents
  documents: [],
  uploadProgress: [],
  
  // Current answer
  currentAnswer: null,
  streamingText: '',
  isStreaming: false,
  isLoading: false,
  statusMessage: '',
  
  // Citations
  activeCitation: null,
  
  // History
  history: [],
  
  // UI state
  error: null,
  webSearchEnabled: false,
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_DOCUMENTS':
      return { ...state, documents: action.payload };
    
    case 'ADD_UPLOAD_PROGRESS':
      return { ...state, uploadProgress: [...state.uploadProgress, action.payload] };
    
    case 'UPDATE_UPLOAD_PROGRESS':
      return {
        ...state,
        uploadProgress: state.uploadProgress.map(p =>
          p.filename === action.payload.filename ? { ...p, ...action.payload } : p
        ),
      };
    
    case 'CLEAR_UPLOAD_PROGRESS':
      return { ...state, uploadProgress: [] };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload, error: null };
    
    case 'SET_STATUS':
      return { ...state, statusMessage: action.payload };
    
    case 'START_STREAMING':
      return { ...state, isStreaming: true, streamingText: '', currentAnswer: null, error: null };
    
    case 'APPEND_TOKEN':
      return { ...state, streamingText: state.streamingText + action.payload };
    
    case 'SET_ANSWER':
      return {
        ...state,
        currentAnswer: action.payload,
        isStreaming: false,
        isLoading: false,
        streamingText: '',
        statusMessage: '',
      };
    
    case 'SET_ACTIVE_CITATION':
      return { ...state, activeCitation: action.payload };
    
    case 'SET_HISTORY':
      return { ...state, history: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false, isStreaming: false };
    
    case 'TOGGLE_WEB_SEARCH':
      return { ...state, webSearchEnabled: !state.webSearchEnabled };
    
    case 'RESET_ANSWER':
      return {
        ...state,
        currentAnswer: null,
        streamingText: '',
        isStreaming: false,
        statusMessage: '',
        activeCitation: null,
        error: null,
      };
    
    default:
      return state;
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // ── API Actions ────────────────────────────────────────

  const fetchDocuments = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/documents');
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_DOCUMENTS', payload: data });
      }
    } catch (e) {
      console.error('Failed to fetch documents:', e);
    }
  }, []);

  const uploadFiles = useCallback(async (files) => {
    dispatch({ type: 'CLEAR_UPLOAD_PROGRESS' });
    
    for (const file of files) {
      dispatch({
        type: 'ADD_UPLOAD_PROGRESS',
        payload: { filename: file.name, status: 'uploading' },
      });

      try {
        const formData = new FormData();
        formData.append('files', file);

        const res = await fetch('/api/v1/ingest', { method: 'POST', body: formData });
        const data = await res.json();

        dispatch({
          type: 'UPDATE_UPLOAD_PROGRESS',
          payload: {
            filename: file.name,
            status: data[0]?.status === 'indexed' ? 'success' : 'error',
            chunks: data[0]?.chunk_count || 0,
          },
        });
      } catch (e) {
        dispatch({
          type: 'UPDATE_UPLOAD_PROGRESS',
          payload: { filename: file.name, status: 'error' },
        });
      }
    }

    // Refresh documents list
    await fetchDocuments();
  }, [fetchDocuments]);

  const askQuestion = useCallback(async (question) => {
    dispatch({ type: 'START_STREAMING' });
    dispatch({ type: 'SET_STATUS', payload: 'Connecting...' });

    try {
      const res = await fetch('/api/v1/ask/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          allow_web_search: state.webSearchEnabled,
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            var eventType = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            switch (eventType) {
              case 'status':
                dispatch({ type: 'SET_STATUS', payload: data });
                break;
              case 'token':
                dispatch({ type: 'APPEND_TOKEN', payload: data });
                break;
              case 'done':
                try {
                  const parsed = JSON.parse(data);
                  dispatch({ type: 'SET_ANSWER', payload: parsed });
                } catch (e) {
                  dispatch({ type: 'SET_ERROR', payload: 'Failed to parse response' });
                }
                break;
              case 'error':
                dispatch({ type: 'SET_ERROR', payload: data });
                break;
            }
          }
        }
      }
    } catch (e) {
      // Fallback to non-streaming
      try {
        dispatch({ type: 'SET_STATUS', payload: 'Using synchronous mode...' });
        const res = await fetch('/api/v1/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question,
            allow_web_search: state.webSearchEnabled,
          }),
        });
        const data = await res.json();
        dispatch({ type: 'SET_ANSWER', payload: data });
      } catch (e2) {
        dispatch({ type: 'SET_ERROR', payload: e2.message });
      }
    }
  }, [state.webSearchEnabled]);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/questions?limit=20');
      if (res.ok) {
        const data = await res.json();
        dispatch({ type: 'SET_HISTORY', payload: data });
      }
    } catch (e) {
      console.error('Failed to fetch history:', e);
    }
  }, []);

  const setActiveCitation = useCallback((marker) => {
    dispatch({ type: 'SET_ACTIVE_CITATION', payload: marker });
  }, []);

  const toggleWebSearch = useCallback(() => {
    dispatch({ type: 'TOGGLE_WEB_SEARCH' });
  }, []);

  const loadHistoryItem = useCallback((item) => {
    dispatch({ type: 'SET_ANSWER', payload: item });
  }, []);

  const value = {
    state,
    dispatch,
    fetchDocuments,
    uploadFiles,
    askQuestion,
    fetchHistory,
    setActiveCitation,
    toggleWebSearch,
    loadHistoryItem,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within AppProvider');
  return context;
}
