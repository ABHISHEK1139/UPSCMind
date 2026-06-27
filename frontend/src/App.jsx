import React, { useState } from 'react';
import AnswerStudio from './components/AnswerStudio';
import Dashboard from './components/Dashboard';
import StudyPlannerPage from './components/StudyPlannerPage';
import NotesPage from './components/NotesPage';
import { MessageSquare, LayoutDashboard, Calendar, FileText, Brain, BarChart3, Settings } from 'lucide-react';

function App() {
  const [activePage, setActivePage] = useState('dashboard');

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'answer', label: 'Answer Studio', icon: MessageSquare },
    { id: 'planner', label: 'Study Planner', icon: Calendar },
    { id: 'notes', label: 'Notes & Flashcards', icon: FileText },
    { id: 'memory', label: 'Memory', icon: Brain },
    { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  ];

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />;
      case 'answer': return <AnswerStudio />;
      case 'planner': return <StudyPlannerPage />;
      case 'notes': return <NotesPage />;
      case 'memory':
        return (
          <div className="card">
            <h2><Brain size={24} /> Knowledge Memory</h2>
            <p>Powered by Qdrant + Neo4j</p>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">2,370</div>
                <div className="stat-label">Knowledge Chunks</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">12</div>
                <div className="stat-label">Graph Entities</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">384</div>
                <div className="stat-label">Embedding Dim</div>
              </div>
            </div>
          </div>
        );
      case 'analytics':
        return (
          <div className="card">
            <h2><BarChart3 size={24} /> Analytics</h2>
            <p>Detailed performance analytics coming soon.</p>
          </div>
        );
      default: return <Dashboard />;
    }
  };

  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-header">
          <Brain color="var(--neon-cyan)" size={28} />
          <div>
            <h1>Hermes</h1>
            <span className="sidebar-subtitle">UPSC AI Mentor</span>
          </div>
        </div>
        <ul className="sidebar-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <li
                key={item.id}
                className={`nav-item ${activePage === item.id ? 'active' : ''}`}
                onClick={() => setActivePage(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </li>
            );
          })}
        </ul>
        <div className="sidebar-footer">
          <div className="nav-item">
            <Settings size={18} />
            <span>Settings</span>
          </div>
        </div>
      </nav>
      <main className="main-content">
        {renderPage()}
      </main>
    </div>
  );
}

export default App
