import { useState, useCallback } from 'react';

const API_BASE = 'http://localhost:8000/api';

export function useHermesAPI() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [streaming, setStreaming] = useState(false);

  const askQuestion = useCallback(async (question, sessionId = 'default-session') => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: sessionId }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `API returned status: ${response.status}`);
      }

      return await response.json();
    } catch (err) {
      console.error('[Hermes API] Error:', err);
      setError(err.message || 'An unknown error occurred');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const askQuestionStream = useCallback(async (question, sessionId, onChunk) => {
    setStreaming(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/answer/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, session_id: sessionId }),
      });

      if (!response.ok) throw new Error(`API returned status: ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try { onChunk?.(JSON.parse(line.slice(6))); } catch {}
          }
        }
      }
    } catch (err) {
      console.error('[Hermes API] Stream error:', err);
      setError(err.message);
    } finally {
      setStreaming(false);
    }
  }, []);

  const getHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/health/detailed`);
      return await response.json();
    } catch {
      return { status: 'unreachable' };
    }
  }, []);

  const getDatasetStats = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/dataset/statistics`);
      return await response.json();
    } catch {
      return null;
    }
  }, []);

  const submitFeedback = useCallback(async (sessionId, rating, corrections = null) => {
    try {
      const response = await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, rating, corrections }),
      });
      return await response.json();
    } catch (err) {
      console.error('[Hermes API] Feedback error:', err);
      return null;
    }
  }, []);

  return {
    askQuestion, askQuestionStream, getHealth, getDatasetStats,
    submitFeedback, loading, streaming, error,
  };
}
