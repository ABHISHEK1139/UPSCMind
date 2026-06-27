import React, { useState, useEffect } from 'react';
import { Calendar, Clock, BookOpen, Target, CheckCircle, Circle, Sun, Moon } from 'lucide-react';

const apiConfig = {
  baseUrl: window.__HERMES_CONFIG__?.baseUrl || 'http://localhost:8000',
};

export default function StudyPlannerPage() {
  const [plan, setPlan] = useState(null);
  const [completedTasks, setCompletedTasks] = useState(new Set());
  const studentId = 'demo-student';

  useEffect(() => {
    fetchStudyPlan();
  }, []);

  const fetchStudyPlan = async () => {
    try {
      const res = await fetch(`${apiConfig.baseUrl}/api/student/study-plan/${studentId}`);
      if (res.ok) {
        const data = await res.json();
        setPlan(data);
      } else {
        setPlan(getMockPlan());
      }
    } catch {
      setPlan(getMockPlan());
    }
  };

  const getMockPlan = () => ({
    student_id: studentId,
    date: new Date().toISOString().split('T')[0],
    phase: 'consolidation',
    days_until_exam: 180,
    total_study_hours: 6.0,
    tasks: [
      { id: 'task-1', title: 'Current Affairs', description: 'Read newspaper + PIB summaries', subject: 'Current Affairs', duration_minutes: 30, priority: 'high', type: 'reading', time_slot: 'morning', completed: false },
      { id: 'task-2', title: 'Revision Block', description: 'Revise weak topics - Polity & Economy', subject: 'Revision', duration_minutes: 90, priority: 'high', type: 'revision', time_slot: 'morning', completed: false },
      { id: 'task-3', title: 'GS2 Study - Governance', description: 'New topic coverage - Governance in India', subject: 'GS2', duration_minutes: 90, priority: 'medium', type: 'reading', time_slot: 'afternoon', completed: false },
      { id: 'task-4', title: 'GS3 Study - Environment', description: 'New topic coverage - Environmental Ecology', subject: 'GS3', duration_minutes: 60, priority: 'medium', type: 'reading', time_slot: 'afternoon', completed: false },
      { id: 'task-5', title: 'Answer Writing Practice', description: 'Write 2 answers and self-evaluate', subject: 'Practice', duration_minutes: 45, priority: 'high', type: 'practice', time_slot: 'evening', completed: false },
      { id: 'task-6', title: 'Evening Review', description: 'Quick review of today\'s study + flashcards', subject: 'Review', duration_minutes: 15, priority: 'medium', type: 'review', time_slot: 'evening', completed: false },
    ],
    summary: {
      current_affairs: '30 min',
      revision: '1.5h',
      new_topics: '2.5h',
      practice: '45 min',
      review: '15 min',
    },
    tips: [
      'Focus on connecting GS2 + GS3 topics for comprehensive understanding',
      'Practice answer writing daily for better presentation',
      'Revise weak topics identified in recent mocks',
    ],
  });

  const toggleTask = (taskId) => {
    setCompletedTasks(prev => {
      const next = new Set(prev);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  const getTimeSlotIcon = (slot) => {
    switch (slot) {
      case 'morning': return <Sun size={16} />;
      case 'evening': return <Moon size={16} />;
      default: return <Clock size={16} />;
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return '#ff6b6b';
      case 'medium': return '#ffd93d';
      default: return '#6bcb77';
    }
  };

  if (!plan) return <div className="loading-spinner">Loading study plan...</div>;

  const progress = plan.tasks.length > 0
    ? Math.round((completedTasks.size / plan.tasks.length) * 100)
    : 0;

  return (
    <div className="planner-container">
      {/* Plan Header */}
      <div className="card planner-header">
        <div className="planner-title">
          <Calendar size={24} />
          <div>
            <h2>Today's Study Plan</h2>
            <span className="plan-date">{plan.date} · {plan.phase} phase · {plan.days_until_exam} days to exam</span>
          </div>
        </div>
        <div className="plan-stats">
          <div className="plan-stat">
            <span className="stat-number">{plan.total_study_hours}h</span>
            <span className="stat-label">Total Study</span>
          </div>
          <div className="plan-stat">
            <span className="stat-number">{completedTasks.size}/{plan.tasks.length}</span>
            <span className="stat-label">Tasks Done</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="card">
        <div className="progress-header">
          <span>Daily Progress</span>
          <span className="progress-percentage">{progress}%</span>
        </div>
        <div className="progress-bar large">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      {/* Time Summary */}
      <div className="time-summary">
        {Object.entries(plan.summary).map(([key, value]) => (
          <div key={key} className="time-chip">
            <span className="time-label">{key.replace('_', ' ')}</span>
            <span className="time-value">{value}</span>
          </div>
        ))}
      </div>

      {/* Tasks */}
      <div className="card">
        <h3><BookOpen size={18} /> Tasks</h3>
        <div className="tasks-list">
          {plan.tasks.map((task) => (
            <div
              key={task.id}
              className={`task-item ${completedTasks.has(task.id) ? 'completed' : ''}`}
              onClick={() => toggleTask(task.id)}
            >
              <div className="task-checkbox">
                {completedTasks.has(task.id)
                  ? <CheckCircle size={20} className="checked" />
                  : <Circle size={20} />
                }
              </div>
              <div className="task-content">
                <div className="task-title">{task.title}</div>
                <div className="task-description">{task.description}</div>
              </div>
              <div className="task-meta">
                <span className="task-slot">{getTimeSlotIcon(task.time_slot)} {task.time_slot}</span>
                <span className="task-duration">{task.duration_minutes} min</span>
                <span className="task-priority" style={{ color: getPriorityColor(task.priority) }}>
                  {task.priority}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tips */}
      <div className="card tips-card">
        <h3><Target size={18} /> Study Tips</h3>
        <ul className="tips-list">
          {plan.tips.map((tip, i) => (
            <li key={i}>{tip}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
