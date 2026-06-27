import React, { useState, useEffect } from 'react';
import { Network, Search, BookOpen, PenTool, CheckCircle, ShieldCheck, MoreHorizontal } from 'lucide-react';

const ICONS = {
  topic_detection: <Network size={16} />,
  retrieval: <Search size={16} />,
  planning: <BookOpen size={16} />,
  draft: <PenTool size={16} />,
  critique: <CheckCircle size={16} />,
  verification: <ShieldCheck size={16} />
};

const LABELS = {
  topic_detection: "1. Topic Detection",
  retrieval: "2. Hybrid Retrieval",
  planning: "3. Framework Planning",
  draft: "4. Answer Drafting",
  critique: "5. Critique & Revise",
  verification: "6. Fact Verification"
};

export default function TrajectoryTree({ trajectory, loading }) {
  const [simulatedSteps, setSimulatedSteps] = useState([]);

  // Simulate progress when loading
  useEffect(() => {
    if (!loading) {
      setSimulatedSteps([]);
      return;
    }
    
    const steps = Object.keys(LABELS);
    let currentStep = 0;
    setSimulatedSteps([steps[0]]);
    
    const interval = setInterval(() => {
      currentStep++;
      if (currentStep < steps.length) {
        setSimulatedSteps(prev => [...prev, steps[currentStep]]);
      }
    }, 4000); // 4 seconds per node
    
    return () => clearInterval(interval);
  }, [loading]);

  if (!trajectory && !loading) {
    return (
      <div className="observatory-section">
        <div className="observatory-header">
          <div className="app-title" style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
            TRAJECTORY TREE: <span style={{ color: 'var(--text-primary)' }}>Awaiting Input</span>
          </div>
          <MoreHorizontal color="var(--text-secondary)" />
        </div>
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
          <p>Waiting for reasoning trajectory...</p>
        </div>
      </div>
    );
  }

  const nodesToRender = trajectory 
    ? Object.keys(trajectory).filter(k => LABELS[k])
    : simulatedSteps;

  return (
    <div className="observatory-section">
      <div className="observatory-header">
        <div className="app-title" style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
          TRAJECTORY TREE: <span style={{ color: 'var(--text-primary)' }}>{loading ? 'Processing Query' : 'Execution Complete'}</span>
        </div>
        <MoreHorizontal color="var(--text-secondary)" />
      </div>

      <div className="tree-container">
        {nodesToRender.map((key, index) => {
          const isLastSimulated = loading && index === simulatedSteps.length - 1;
          const isProcessing = loading && isLastSimulated;
          const nodeData = trajectory ? trajectory[key] : null;
          
          return (
            <div key={key} className="tree-node-wrapper">
              <div className={`tree-node ${isProcessing ? 'processing' : ''}`}>
                <div className="tree-node-header">
                  {LABELS[key]}
                </div>
                
                <div className="node-status-text">
                  <div className={`node-status-icon ${isProcessing ? 'processing' : 'complete'}`}>
                    {isProcessing ? <Network size={12} /> : <CheckCircle size={12} />}
                  </div>
                  {isProcessing ? 'Processing' : 'Complete'}
                </div>
                
                {/* Real Data Snippets */}
                {nodeData && (
                  <div className="node-details">
                    {key === 'topic_detection' && <div>Topic: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.output || 'UPSC'}</span></div>}
                    {key === 'retrieval' && <div>Chunks: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.chunks_retrieved || 0}</span></div>}
                    {key === 'planning' && <div>Format: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.framework || 'Standard'}</span></div>}
                    {key === 'draft' && <div>Tokens: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.tokens || 0}</span></div>}
                    {key === 'critique' && <div>Score: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.quality_score || 'N/A'}</span></div>}
                    {key === 'verification' && <div>Passed: <span style={{color: 'var(--neon-cyan)'}}>{nodeData.guardrails_pass ? 'Yes' : 'No'}</span></div>}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
