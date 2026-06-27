import React, { useState, useEffect } from 'react';
import { BookOpen, TrendingUp, Clock, Target, Flame, Award, Calendar, BarChart3 } from 'lucide-react';

const apiConfig = {
  baseUrl: window.__HERMES_CONFIG__?.baseUrl || 'http://localhost:8000',
  get answerUrl() { return `${this.baseUrl}/api/answer`; },
  get healthUrl() { return `${this.baseUrl}/api/health`; },
};

export default function Dashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const studentId = 'demo-student';

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${apiConfig.baseUrl}/api/student/dashboard/${studentId}`);
      if (res.ok) {
        const data = await res.json();
        setDashboardData(data);
      } else {
        setDashboardData(getMockDashboard());
      }
    } catch {
      setDashboardData(getMockDashboard());
    } finally {
      setLoading(false);
    }
  };

  const getMockDashboard = () => ({
    student_id: studentId,
    generated_at: new Date().toISOString(),
    overall_progress: {
      gs1_score: 62, gs2_score: 58, gs3_score: 71, gs4_score: 65, essay_score: 60,
      overall_score: 63.2, percentile: 70,
    },
    subject_breakdown: {
      gs1: { score: 62, topics_covered: 31, total_topics: 50, color: '#667eea' },
      gs2: { score: 58, topics_covered: 29, total_topics: 50, color: '#764ba2' },
      gs3: { score: 71, topics_covered: 35, total_topics: 50, color: '#f093fb' },
      gs4: { score: 65, topics_covered: 32, total_topics: 50, color: '#4facfe' },
      essay: { score: 60, topics_covered: 12, total_topics: 20, color: '#43e97b' },
    },
    activity_7_days: [
      { date: '2026-06-20', day: 'Fri', study_minutes: 240, questions_attempted: 5, answers_written: 3, revisions_done: 8 },
      { date: '2026-06-21', day: 'Sat', study_minutes: 180, questions_attempted: 3, answers_written: 2, revisions_done: 5 },
      { date: '2026-06-22', day: 'Sun', study_minutes: 300, questions_attempted: 7, answers_written: 4, revisions_done: 10 },
      { date: '2026-06-23', day: 'Mon', study_minutes: 120, questions_attempted: 2, answers_written: 1, revisions_done: 3 },
      { date: '2026-06-24', day: 'Tue', study_minutes: 270, questions_attempted: 6, answers_written: 3, revisions_done: 7 },
      { date: '2026-06-25', day: 'Wed', study_minutes: 200, questions_attempted: 4, answers_written: 2, revisions_done: 6 },
      { date: '2026-06-26', day: 'Thu', study_minutes: 150, questions_attempted: 3, answers_written: 2, revisions_done: 4 },
    ],
    weak_topics: [
      { topic: 'Federalism', subject: 'GS2', score: 35 },
      { topic: 'Monetary Policy', subject: 'GS3', score: 40 },
      { topic: 'Ancient History', subject: 'GS1', score: 42 },
    ],
    strong_topics: [
      { topic: 'Fundamental Rights', subject: 'GS2', score: 85 },
      { topic: 'Climate Change', subject: 'GS3', score: 82 },
      { topic: 'Ethics in Administration', subject: 'GS4', score: 78 },
    ],
    revision_due: [
      { topic: 'Polity - Separation of Powers', subject: 'GS2', due_date: '2026-06-26' },
      { topic: 'Economy - Fiscal Policy', subject: 'GS3', due_date: '2026-06-26' },
    ],
    streak: { current: 7, longest: 15, last_activity: '2026-06-26T10:30:00Z' },
    study_time: { today_hours: 2.5, week_hours: 15.6, month_hours: 62.4, total_hours: 186.5 },
    recommendations: [
      'Focus on GS2 — it\'s your weakest paper',
      'Revise Modern History — due for revision',
      'Practice 1 answer daily for better scores',
      'Complete Economy syllabus by end of month',
    ],
  });

  if (loading) return <div className="loading-spinner">Loading dashboard...</div>;

  const data = dashboardData || getMockDashboard();

  return (
    <div className="dashboard-container">
      {/* Header Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <Flame className="stat-icon" size={24} />
          <div className="stat-value">{data.streak?.current || 0}</div>
          <div className="stat-label">Day Streak</div>
        </div>
        <div className="stat-card">
          <TrendingUp className="stat-icon" size={24} />
          <div className="stat-value">{data.overall_progress?.overall_score || 0}%</div>
          <div className="stat-label">Overall Score</div>
        </div>
        <div className="stat-card">
          <Clock className="stat-icon" size={24} />
          <div className="stat-value">{data.study_time?.today_hours || 0}h</div>
          <div className="stat-label">Today's Study</div>
        </div>
        <div className="stat-card">
          <Target className="stat-icon" size={24} />
          <div className="stat-value">{data.overall_progress?.percentile || 0}</div>
          <div className="stat-label">Percentile</div>
        </div>
      </div>

      {/* Subject Progress */}
      <div className="card">
        <h2><BarChart3 size={20} /> Subject-wise Progress</h2>
        <div className="subject-grid">
          {data.subject_breakdown && Object.entries(data.subject_breakdown).map(([key, subject]) => (
            <div key={key} className="subject-card">
              <div className="subject-header">
                <span className="subject-name">{key.toUpperCase()}</span>
                <span className="subject-score" style={{ color: subject.color }}>{subject.score}%</span>
              </div>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${subject.score}%`, backgroundColor: subject.color }} />
              </div>
              <div className="subject-detail">{subject.topics_covered}/{subject.total_topics} topics</div>
            </div>
          ))}
        </div>
      </div>

      {/* Activity Chart */}
      <div className="card">
        <h2><Calendar size={20} /> 7-Day Activity</h2>
        <div className="activity-chart">
          {data.activity_7_days?.map((day, i) => (
            <div key={i} className="activity-bar-container">
              <div className="activity-bar" style={{ height: `${Math.max(10, day.study_minutes / 5)}px` }} />
              <div className="activity-label">{day.day}</div>
              <div className="activity-minutes">{day.study_minutes}m</div>
            </div>
          ))}
        </div>
      </div>

      {/* Weak & Strong Topics */}
      <div className="two-column">
        <div className="card">
          <h2><Target size={20} /> Weak Topics</h2>
          {data.weak_topics?.map((topic, i) => (
            <div key={i} className="topic-item weak">
              <span className="topic-name">{topic.topic}</span>
              <span className="topic-score">{topic.score}%</span>
            </div>
          ))}
        </div>
        <div className="card">
          <h2><Award size={20} /> Strong Topics</h2>
          {data.strong_topics?.map((topic, i) => (
            <div key={i} className="topic-item strong">
              <span className="topic-name">{topic.topic}</span>
              <span className="topic-score">{topic.score}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recommendations */}
      <div className="card">
        <h2><BookOpen size={20} /> Recommendations</h2>
        <ul className="recommendations-list">
          {data.recommendations?.map((rec, i) => (
            <li key={i}>{rec}</li>
          ))}
        </ul>
      </div>

      {/* Revision Due */}
      {data.revision_due?.length > 0 && (
        <div className="card revision-due">
          <h2><Clock size={20} /> Revision Due</h2>
          {data.revision_due.map((item, i) => (
            <div key={i} className="revision-item">
              <span>{item.topic}</span>
              <span className="revision-badge">Due</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
