import React, { useState, useEffect, useCallback } from 'react';
import { Activity, Database, Cpu, Clock, CheckCircle, XCircle, BarChart3 } from 'lucide-react';

export default function BenchmarkDashboard() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [healthRes, statsRes] = await Promise.all([
        fetch('http://localhost:8000/api/health/detailed').then(r => r.json()).catch(() => null),
        fetch('http://localhost:8000/api/dataset/statistics').then(r => r.json()).catch(() => null),
      ]);
      setHealth(healthRes);
      setStats(statsRes);
    } catch (err) {
      console.error('[Dashboard] Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) return <div className="dashboard-loading">Loading dashboard...</div>;

  return (
    <div className="benchmark-dashboard">
      <h2><BarChart3 size={24} /> System Dashboard</h2>
      
      {/* ── Health Status ──────────────────────────────────── */}
      <section className="dashboard-section">
        <h3><Activity size={18} /> Service Health</h3>
        <div className="health-grid">
          {health?.checks && Object.entries(health.checks).map(([name, info]) => (
            <div key={name} className={`health-card ${info.status}`}>
              <div className="health-icon">
                {info.status === 'healthy' ? <CheckCircle size={20} /> : <XCircle size={20} />}
              </div>
              <div className="health-info">
                <span className="health-name">{name}</span>
                <span className="health-status">{info.status}</span>
              </div>
            </div>
          ))}
        </div>
        {health?.response_time_ms && (
          <p className="response-time">Health check: {health.response_time_ms}ms</p>
        )}
      </section>

      {/* ── Dataset Statistics ─────────────────────────────── */}
      <section className="dashboard-section">
        <h3><Database size={18} /> Training Data</h3>
        {stats?.statistics ? (
          <div className="stats-grid">
            {Object.entries(stats.statistics).map(([filename, fileStats]) => (
              <div key={filename} className="stat-card">
                <h4>{filename}</h4>
                <div className="stat-row">
                  <span>Total Records</span>
                  <strong>{fileStats.total || 0}</strong>
                </div>
                {fileStats.avg_score && (
                  <div className="stat-row">
                    <span>Avg Score</span>
                    <strong className={fileStats.avg_score >= 0.9 ? 'good' : fileStats.avg_score >= 0.7 ? 'ok' : 'poor'}>
                      {fileStats.avg_score.toFixed(3)}
                    </strong>
                  </div>
                )}
                {fileStats.domains && Object.entries(fileStats.domains).map(([dom, cnt]) => (
                  <div key={dom} className="stat-row domain">
                    <span>{dom}</span>
                    <span>{cnt}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-muted">No training data yet. Generate some answers first.</p>
        )}
      </section>

      {/* ── Quick Actions ──────────────────────────────────── */}
      <section className="dashboard-section">
        <h3><Cpu size={18} /> Quick Actions</h3>
        <div className="action-buttons">
          <button className="action-btn" onClick={fetchData}>
            <Activity size={16} /> Refresh
          </button>
          <button className="action-btn" onClick={() => fetch('http://localhost:8000/api/benchmark/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ n_questions: 50 }),
          })}>
            <Clock size={16} /> Run Quick Benchmark (50)
          </button>
          <button className="action-btn" onClick={() => fetch('http://localhost:8000/api/dataset/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ min_score: 0.9 }),
          })}>
            <Database size={16} /> Export Dataset
          </button>
        </div>
      </section>
    </div>
  );
}
