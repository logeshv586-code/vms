import React from 'react';
import './PTZControl.css';

const PARAMETERS = [
  ['Crowd threshold', 'Minimum visible person count before the crowd rule becomes a candidate.', 'Pattern / temporal'],
  ['Loitering time', 'How long one tracked person remains in an area before a loitering candidate is created.', 'Track history'],
  ['Persistence time', 'How long a target must remain in a restricted zone before intrusion is promoted.', 'Zone + tracking'],
  ['Unattended object time', 'How long an eligible object remains stationary without a nearby owner.', 'Object + temporal'],
  ['Detection confidence', 'YOLO object confidence cutoff. Lower values increase recall but also false detections.', 'YOLO Layer 1'],
  ['Gemma verification', 'Semantic Layer 3 validates contextual candidates; it must not invent duration, identity or zone facts.', 'Semantic verifier'],
  ['Event deduplication', 'Prevents one continuous situation from creating a new alert every processed frame.', 'Event pipeline'],
  ['Face threshold', 'Identity matching threshold must be calibrated with labelled camera data; it is separate from face detection.', 'Face recognition']
];

const EventParametersGuide = () => (
  <div className="ptz-page">
    <div className="ptz-header">
      <div>
        <h2>Event Parameters</h2>
        <p>These parameters control when raw detections become candidates or alerts. They are different from turning a rule ON/OFF for a camera.</p>
      </div>
      <span className="ptz-status">REFERENCE</span>
    </div>

    <div className="ptz-message warning">
      Keep thresholds evidence-based. Changing a value because one test clip “looks better” can increase false alerts on other cameras. Use labelled day/night camera clips before changing production thresholds.
    </div>

    <div className="ptz-card">
      <h3>How the parameters fit the pipeline</h3>
      <div className="events-table-wrapper">
        <table className="events-table">
          <thead><tr><th>Parameter</th><th>What it changes</th><th>Layer</th></tr></thead>
          <tbody>
            {PARAMETERS.map(([name, description, layer]) => (
              <tr key={name}><td><strong>{name}</strong></td><td>{description}</td><td>{layer}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="ptz-explainer">
        <strong>Configuration rule</strong>
        <p>Detection Rule Set decides whether a feature is available globally. Rules On Camera decides where it runs. Event Parameters tune how that enabled feature behaves. Runtime DETECTING additionally requires a healthy stream/model.</p>
      </div>
    </div>
  </div>
);

export default EventParametersGuide;
