import React, { useState, useCallback } from 'react';
import ChatInterface from './ChatInterface';
import TrajectoryTree from './TrajectoryTree';
import BenchmarkDashboard from './BenchmarkDashboard';
import { useHermesAPI } from '../hooks/useHermesAPI';
import { useWebSocket } from '../hooks/useWebSocket';
import { Settings, History, MessageSquare, Hexagon, BarChart3, Zap } from 'lucide-react';

export default function AnswerStudio() {
  const [messages, setMessages] = useState([]);
  const [latestTrajectory, setLatestTrajectory] = useState(null);
  const [latestResponse, setLatestResponse] = useState(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [sessionId] = useState(`session-${Date.now()}`);
  
  const { askQuestion, loading, error } = useHermesAPI();
  const { connected, events } = useWebSocket(sessionId);

  const handleSendMessage = useCallback(async (text) => {
    const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLatestTrajectory(null);
    setLatestResponse(null);

    const response = await askQuestion(text, sessionId);

    if (response && response.answer) {
      setMessages((prev) => [...prev, {
        role: 'assistant', content: response.answer,
        timestamp: new Date().toISOString(),
        metadata: { domain: response.domain, score: response.critique_score, revisions: response.revision_iterations },
      }]);
      setLatestTrajectory(response.cot_trace || []);
      setLatestResponse(response);
    } else {
      setMessages((prev) => [...prev, {
        role: 'assistant', content: `**Error:** ${error || 'Failed to get a response.'}`,
        timestamp: new Date().toISOString(), isError: true,
      }]);
    }
  }, [askQuestion, sessionId, error]);

  return (
    <div className="layout-container">
      <div className="app-frame">
        <header className="app-header">
          <div className="app-title">
            <Hexagon color="var(--neon-cyan)" fill="var(--neon-cyan-dim)" size={28} />
            <div><h1>Hermes V2</h1><span className="subtitle">UPSC Intelligence System</span></div>
          </div>
          <div className="header-status">
            <div className={`status-dot ${connected ? 'online' : 'offline'}`} />
            <span>{connected ? 'Live' : 'Offline'}</span>
          </div>
          <nav className="app-nav">
            <div className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')}>
              <MessageSquare size={18} /> Chat
            </div>
            <div className={`nav-item ${activeTab === 'benchmark' ? 'active' : ''}`} onClick={() => setActiveTab('benchmark')}>
              <BarChart3 size={18} /> Benchmark
            </div>
            <div className={`nav-item ${activeTab === 'history' ? 'active' : ''}`} onClick={() => setActiveTab('history')}>
              <History size={18} /> History
            </div>
            <div className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
              <Settings size={18} /> Settings
            </div>
          </nav>
        </header>
        
        <div className="app-body">
          {activeTab === 'chat' && (
            <>
              <ChatInterface messages={messages} onSendMessage={handleSendMessage} loading={loading} latestResponse={latestResponse} />
              <TrajectoryTree trajectory={latestTrajectory} loading={loading} wsEvents={events} />
            </>
          )}
          {activeTab === 'benchmark' && <BenchmarkDashboard />}
          {activeTab === 'history' && (
            <div className="history-panel">
              <h3>Session History</h3>
              <p className="text-muted">Session: {sessionId}</p>
              <div className="history-stats">
                <div className="stat-card"><Zap size={20} /><span>{messages.filter(m => m.role === 'user').length} Questions</span></div>
                <div className="stat-card"><Hexagon size={20} /><span>{messages.filter(m => m.role === 'assistant' && !m.isError).length} Answers</span></div>
              </div>
            </div>
          )}
          {activeTab === 'settings' && (
            <div className="settings-panel">
              <h3>Settings</h3>
              <div className="setting-item"><label>Session ID</label><input type="text" value={sessionId} readOnly /></div>
              <div className="setting-item"><label>WebSocket</label><span className={connected ? 'status-online' : 'status-offline'}>{connected ? 'Connected' : 'Disconnected'}</span></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}{loading} 
          />
          
          <TrajectoryTree 
            trajectory={latestTrajectory} 
            loading={loading} 
          />
        </div>
        
        {error && (
          <div style={{ position: 'absolute', bottom: '20px', right: '20px', background: 'var(--danger-red)', padding: '16px', borderRadius: '8px', zIndex: 1000, boxShadow: '0 4px 20px rgba(255, 51, 102, 0.4)' }}>
            <strong>Connection Error:</strong> {error}
          </div>
        )}
      </div>
    </div>
  );
}
