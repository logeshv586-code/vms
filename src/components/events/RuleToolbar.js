import React from 'react';
import './RuleToolbar.css';

const RuleToolbar = ({ rules, enabledRules, selectedRules, onRuleToggle }) => {
  // Create a mapping of rule IDs to rule names for tooltips
  const ruleNameMap = rules.reduce((map, rule) => {
    map[rule.id] = rule.name;
    return map;
  }, {});

  const isRuleEnabled = (ruleId) => enabledRules.includes(ruleId);
  const isRuleSelected = (ruleId) => selectedRules.includes(ruleId);

  const handleRuleClick = (ruleId) => {
    // Only allow toggling if the rule is enabled
    if (isRuleEnabled(ruleId)) {
      onRuleToggle(ruleId);
    }
  };

  return (
    <div className="rule-toolbar">
      <div className="rule-toolbar-header">
        <h3>Detection Rule Shortcuts</h3>
        <p>Click to select rules to apply (only enabled rules can be selected)</p>
      </div>

      <div className="rule-buttons">
        {Array.from({ length: 23 }, (_, i) => i + 1).map(ruleId => (
          <button
            key={ruleId}
            className={`rule-button ${isRuleEnabled(ruleId) ? 'enabled' : 'disabled'} ${isRuleSelected(ruleId) ? 'selected' : ''}`}
            onClick={() => handleRuleClick(ruleId)}
            disabled={!isRuleEnabled(ruleId)}
            title={!isRuleEnabled(ruleId) ? 'Disabled - Enable in Detection Rule Set' : ''}
          >
            {ruleId}. {ruleNameMap[ruleId] || `Rule ${ruleId}`}
          </button>
        ))}
      </div>

      <div className="selected-rules">
        <span>Selected Rules: </span>
        {selectedRules.length === 0 ? (
          <span className="no-rules-selected">None</span>
        ) : (
          <div className="selected-rule-tags">
            {selectedRules.map(ruleId => (
              <div key={ruleId} className="rule-tag">
                {ruleId}. {ruleNameMap[ruleId]}
                <button
                  className="remove-rule"
                  onClick={() => onRuleToggle(ruleId)}
                  title="Remove rule"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default RuleToolbar;
