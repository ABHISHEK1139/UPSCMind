import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Paperclip, Mic, Settings, Activity } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

export default function ChatInterface({ messages, onSendMessage, loading }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = () => {
    if (input.trim() && !loading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-section">
      <div className="chat-header">
        <div className="app-title" style={{ fontSize: '1.1rem' }}>
          <div style={{ background: 'var(--neon-cyan-dim)', padding: '6px', borderRadius: '50%' }}>
            <Bot color="var(--neon-cyan)" size={20} />
          </div>
          Hermes V2
        </div>
        <div className="status-indicator">
          Status: <span style={{ color: 'var(--text-primary)' }}>Online</span>
          <div className="status-dot"></div>
        </div>
      </div>
      
      <div className="messages-container">
        {messages.length === 0 ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            <div style={{ textAlign: 'center', maxWidth: '300px' }}>
              <Activity size={48} style={{ opacity: 0.2, margin: '0 auto 16px', color: 'var(--neon-cyan)' }} />
              <p>Hermes V2 initialized. Secure connection established. Awaiting query...</p>
            </div>
          </div>
        ) : (
          messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role}`}>
              {msg.role === 'assistant' ? (
                <div className="markdown-body" style={{fontSize: '0.95rem'}}>
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <div style={{ fontSize: '1rem', fontWeight: 500 }}>{msg.content}</div>
              )}
            </div>
          ))
        )}
        
        {loading && (
          <div className="message assistant">
            <span className="loading-dots" style={{ color: 'var(--neon-cyan)', fontWeight: 600 }}>Analyzing data stream</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <div className="input-container">
          <textarea
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Analyze quantum encryption market growth..."
            rows={1}
            disabled={loading}
          />
          <div className="chat-actions">
            <button className="icon-btn"><Paperclip size={20} /></button>
            <button className="icon-btn"><Mic size={20} /></button>
            <button className="icon-btn"><Settings size={20} /></button>
            <button 
              className="send-button"
              onClick={handleSend}
              disabled={!input.trim() || loading}
            >
              <Send size={18} strokeWidth={3} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
