import React, { useState, useEffect } from 'react';
import './PerformanceMetrics.css';

function PerformanceMetrics() {
  const [cpu, setCpu] = useState(0);
  const [memory, setMemory] = useState(0);

  useEffect(() => {
    let interval;
    function updateMetrics() {
      const proc = typeof process !== 'undefined' ? process : null;
      const perf = typeof window !== 'undefined' && window.performance ? window.performance : null;

      const cpuUsage = proc && proc.getCPUUsage ? proc.getCPUUsage().percentCPUUsage : 0;
      const memUsage = proc && proc.memoryUsage ? proc.memoryUsage().rss : (perf && perf.memory ? perf.memory.usedJSHeapSize : 0);

      setCpu(typeof cpuUsage === 'number' ? cpuUsage.toFixed(1) : '0.0');
      setMemory(typeof memUsage === 'number' ? (memUsage / (1024 * 1024)).toFixed(1) : '0.0');
    }
    updateMetrics();
    // Update more frequently for dynamic display (every 500ms instead of 1000ms)
    interval = setInterval(updateMetrics, 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="performance-metrics">
      <div className="metric-item">
        <span className="metric-text" style={{ color: '#ffffff' }}>CPU: {cpu}%</span>
      </div>
      <div className="metric-item">
        <span className="metric-text" style={{ color: '#ffffff' }}>Memory: {memory} MB</span>
      </div>
    </div>
  );
}

export default PerformanceMetrics;