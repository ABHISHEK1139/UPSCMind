import React, { useState } from 'react';
import { FileText, Zap, BookOpen, Brain, Download, RefreshCw } from 'lucide-react';

export default function NotesPage() {
  const [topic, setTopic] = useState('');
  const [content, setContent] = useState('');
  const [notes, setNotes] = useState(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState('input'); // input, notes, flashcards, mindmap

  const generateNotes = async () => {
    if (!topic || !content) return;
    setLoading(true);

    try {
      const res = await fetch('/api/student/notes/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, content, source: 'answer' }),
      });

      if (res.ok) {
        const data = await res.json();
        setNotes(data);
        setView('notes');
      } else {
        setNotes(getMockNotes(topic, content));
        setView('notes');
      }
    } catch {
      setNotes(getMockNotes(topic, content));
      setView('notes');
    } finally {
      setLoading(false);
    }
  };

  const getMockNotes = (topic, content) => ({
    id: 'notes-' + Date.now(),
    topic,
    summary: `Comprehensive notes on ${topic}: Key concepts include constitutional provisions, historical context, and contemporary relevance. The topic covers fundamental aspects that are crucial for UPSC preparation.`,
    key_points: [
      { point: 'Core concept and definition', importance: 'high', category: 'concept' },
      { point: 'Constitutional provisions and articles', importance: 'high', category: 'article' },
      { point: 'Historical background and evolution', importance: 'medium', category: 'fact' },
      { point: 'Recent developments and current affairs', importance: 'high', category: 'data' },
      { point: 'Government schemes and programs', importance: 'medium', category: 'scheme' },
      { point: 'Critical analysis and way forward', importance: 'high', category: 'concept' },
    ],
    flashcards: [
      { front: `What is the significance of ${topic}?`, back: `${topic} is a critical topic for UPSC, covering constitutional, social, and economic dimensions.`, difficulty: 'medium' },
      { front: 'Key constitutional provisions related to ' + topic, back: 'Important articles and amendments form the legal framework.', difficulty: 'medium' },
      { front: 'Recent developments in ' + topic, back: 'Current affairs integration shows contemporary relevance.', difficulty: 'hard' },
    ],
    mindmap: {
      central_node: topic,
      branches: [
        { label: 'Key Concepts', nodes: [{ id: '1', label: 'Definition', category: 'concept' }, { id: '2', label: 'Scope', category: 'concept' }] },
        { label: 'Provisions', nodes: [{ id: '3', label: 'Constitutional', category: 'article' }, { id: '4', label: 'Legal', category: 'article' }] },
        { label: 'Facts', nodes: [{ id: '5', label: 'Data Points', category: 'data' }, { id: '6', label: 'Statistics', category: 'data' }] },
      ],
    },
  });

  return (
    <div className="notes-container">
      {/* Input Section */}
      <div className="card">
        <h2><FileText size={20} /> Notes Generator</h2>
        <div className="form-group">
          <label>Topic</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="e.g., Fundamental Rights, Fiscal Policy, Climate Change"
          />
        </div>
        <div className="form-group">
          <label>Content / Answer</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste your answer, notes, or study material here..."
            rows={8}
          />
        </div>
        <button className="btn-primary" onClick={generateNotes} disabled={loading || !topic || !content}>
          {loading ? <RefreshCw size={16} className="spin" /> : <Zap size={16} />}
          {loading ? 'Generating...' : 'Generate Notes'}
        </button>
      </div>

      {/* View Tabs */}
      {notes && (
        <>
          <div className="view-tabs">
            <button className={`tab ${view === 'notes' ? 'active' : ''}`} onClick={() => setView('notes')}>
              <FileText size={16} /> Notes
            </button>
            <button className={`tab ${view === 'flashcards' ? 'active' : ''}`} onClick={() => setView('flashcards')}>
              <BookOpen size={16} /> Flashcards
            </button>
            <button className={`tab ${view === 'mindmap' ? 'active' : ''}`} onClick={() => setView('mindmap')}>
              <Brain size={16} /> Mindmap
            </button>
          </div>

          {/* Notes View */}
          {view === 'notes' && (
            <div className="card">
              <h3>Summary</h3>
              <p className="notes-summary">{notes.summary}</p>
              <h4>Key Points</h4>
              <div className="key-points-list">
                {notes.key_points?.map((kp, i) => (
                  <div key={i} className="key-point-item">
                    <div className="kp-header">
                      <span className="kp-category">{kp.category}</span>
                      <span className={`kp-importance ${kp.importance}`}>{kp.importance}</span>
                    </div>
                    <p>{kp.point}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Flashcards View */}
          {view === 'flashcards' && (
            <div className="card">
              <h3>Flashcards</h3>
              <div className="flashcards-grid">
                {notes.flashcards?.map((fc, i) => (
                  <div key={i} className="flashcard">
                    <div className="flashcard-front">
                      <span className="fc-number">Q{i + 1}</span>
                      <p>{fc.front}</p>
                    </div>
                    <div className="flashcard-back">
                      <span className="fc-number">A{i + 1}</span>
                      <p>{fc.back}</p>
                      <span className={`fc-difficulty ${fc.difficulty}`}>{fc.difficulty}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Mindmap View */}
          {view === 'mindmap' && (
            <div className="card">
              <h3>Mindmap: {notes.mindmap?.central_node}</h3>
              <div className="mindmap-container">
                <div className="mindmap-center">{notes.mindmap?.central_node}</div>
                <div className="mindmap-branches">
                  {notes.mindmap?.branches?.map((branch, i) => (
                    <div key={i} className="mindmap-branch">
                      <div className="branch-label">{branch.label}</div>
                      <div className="branch-nodes">
                        {branch.nodes.map((node, j) => (
                          <div key={j} className="mindmap-node">{node.label}</div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
