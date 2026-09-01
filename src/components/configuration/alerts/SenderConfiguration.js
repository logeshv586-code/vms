import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../../utils/apiConfig';
import { fetchAlertsConfig, updateAlertsConfig } from '../../../services/alertsService';
import './SenderConfiguration.css';

const SenderConfiguration = ({ selectedMenu }) => {
  // Only render content when Sender Configuration menu is selected
  if (selectedMenu !== 'sender-configuration') {
    return null;
  }

  // State for alert configuration
  const [alertConfig, setAlertConfig] = useState({
    alertType: 'email', // Default to email only
    email: {
      senderEmail: '',
      senderPassword: '',
      supportEmail: '',
      mailServer: '',
      port: '',
      authentication: 'SSL/TLS' // Default authentication type
    },
    sms: {
      senderPhone: '',
      gatewayUrl: '',
      apiKey: '',
      receiverPhones: '',
      messageTemplate: ''
    }
  });

  // State for error handling and saving
  const [error, setError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  // State for collapsible sections (only relevant when both SMS and Email are selected)
  const [expandedSections, setExpandedSections] = useState({
    email: true,
    sms: true
  });

  // Toggle section expansion
  const toggleSection = (section) => {
    if (alertConfig.alertType === 'both') {
      setExpandedSections(prev => ({
        ...prev,
        [section]: !prev[section]
      }));
    }
  };

  // Fetch alert configuration on component mount (background loading)
  useEffect(() => {
    const getAlertConfig = async () => {
      try {
        const response = await fetchAlertsConfig();

        if (response && response.success) {
          setAlertConfig(response.data || {
            alertType: 'email',
            email: {
              senderEmail: '',
              senderPassword: '',
              supportEmail: '',
              mailServer: '',
              port: '',
              authentication: 'SSL/TLS'
            },
            sms: {
              senderPhone: '',
              gatewayUrl: '',
              apiKey: '',
              receiverPhones: '',
              messageTemplate: ''
            }
          });
        } else {
          setError('Failed to load alert configuration');
        }
      } catch (err) {
        console.error('Error fetching alert configuration:', err);
        setError('Failed to connect to the server. Please try again later.');
      }
    };

    getAlertConfig();
  }, []);

  // Handle alert type change
  const handleAlertTypeChange = (type) => {
    setAlertConfig({
      ...alertConfig,
      alertType: type
    });

    // If switching to 'both', expand both sections
    if (type === 'both') {
      setExpandedSections({
        email: true,
        sms: true
      });
    }
  };

  // Handle email settings change
  const handleEmailChange = (e) => {
    const { name, value } = e.target;
    setAlertConfig({
      ...alertConfig,
      email: {
        ...alertConfig.email,
        [name]: value
      }
    });
  };

  // Handle SMS settings change
  const handleSmsChange = (e) => {
    const { name, value } = e.target;
    setAlertConfig({
      ...alertConfig,
      sms: {
        ...alertConfig.sms,
        [name]: value
      }
    });
  };

  // Handle authentication type change
  const handleAuthChange = (e) => {
    setAlertConfig({
      ...alertConfig,
      email: {
        ...alertConfig.email,
        authentication: e.target.value
      }
    });
  };

  // Handle test SMS sending
  const handleSendTestSms = (e) => {
    e.preventDefault();
    // This would typically call an API to send a test SMS
    alert('Test SMS functionality would be implemented here');
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setSaveSuccess(false);
    setError(null);

    try {
      const response = await updateAlertsConfig(alertConfig);

      if (response && response.success) {
        setSaveSuccess(true);
        // Hide success message after 3 seconds
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        setError(response?.error || 'Failed to save configuration');
      }
    } catch (err) {
      console.error('Error saving alert configuration:', err);
      setError('Failed to connect to the server. Please try again later.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="sender-config-container">
      <div className="sender-config-header">
        <h2>Sender Configuration</h2>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="alert-type-section">
          <h3>Active Alert Type</h3>
          <div className="alert-type-options">
            <label className="alert-type-option">
              <input
                type="radio"
                name="alertType"
                checked={alertConfig.alertType === 'sms'}
                onChange={() => handleAlertTypeChange('sms')}
              />
              <span className="radio-label">SMS Only</span>
            </label>
            <label className="alert-type-option">
              <input
                type="radio"
                name="alertType"
                checked={alertConfig.alertType === 'email'}
                onChange={() => handleAlertTypeChange('email')}
              />
              <span className="radio-label">Email Only</span>
            </label>
            <label className="alert-type-option">
              <input
                type="radio"
                name="alertType"
                checked={alertConfig.alertType === 'both'}
                onChange={() => handleAlertTypeChange('both')}
              />
              <span className="radio-label">SMS & Email Both</span>
            </label>
          </div>
        </div>

        {/* Email Settings Section */}
        {(alertConfig.alertType === 'email' || alertConfig.alertType === 'both') && (
          <div className="settings-section">
            <div
              className="settings-header"
              onClick={() => toggleSection('email')}
            >
              <h3>Email Settings</h3>
              {alertConfig.alertType === 'both' && (
                <span className="toggle-icon">
                  {expandedSections.email ? '▼' : '▶'}
                </span>
              )}
            </div>
            <div className={`settings-content ${alertConfig.alertType === 'both' && !expandedSections.email ? 'collapsed' : ''}`}>
              <div className="form-group">
                <label htmlFor="senderEmail">Sender Email ID</label>
                <input
                  type="email"
                  id="senderEmail"
                  name="senderEmail"
                  value={alertConfig.email.senderEmail}
                  onChange={handleEmailChange}
                  placeholder="example@domain.com"
                  required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="senderPassword">Sender Password</label>
                <input
                  type="password"
                  id="senderPassword"
                  name="senderPassword"
                  value={alertConfig.email.senderPassword}
                  onChange={handleEmailChange}
                  placeholder="••••••••"
                  required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="supportEmail">Support Email ID</label>
                <input
                  type="email"
                  id="supportEmail"
                  name="supportEmail"
                  value={alertConfig.email.supportEmail}
                  onChange={handleEmailChange}
                  placeholder="support@domain.com"
                  required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-row">
                <div className="form-group half">
                  <label htmlFor="mailServer">Mail Server</label>
                  <input
                    type="text"
                    id="mailServer"
                    name="mailServer"
                    value={alertConfig.email.mailServer}
                    onChange={handleEmailChange}
                    placeholder="smtp.gmail.com"
                    required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                  />
                </div>
                <div className="form-group half">
                  <label htmlFor="port">Port</label>
                  <input
                    type="text"
                    id="port"
                    name="port"
                    value={alertConfig.email.port}
                    onChange={handleEmailChange}
                    placeholder="465"
                    required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                  />
                </div>
              </div>
              <div className="form-group">
                <label htmlFor="authentication">Authentication</label>
                <select
                  id="authentication"
                  name="authentication"
                  value={alertConfig.email.authentication}
                  onChange={handleAuthChange}
                  required={alertConfig.alertType === 'email' || alertConfig.alertType === 'both'}
                >
                  <option value="None">None</option>
                  <option value="SSL/TLS">SSL/TLS</option>
                  <option value="STARTTLS">STARTTLS</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* SMS Settings Section */}
        {(alertConfig.alertType === 'sms' || alertConfig.alertType === 'both') && (
          <div className="settings-section">
            <div
              className="settings-header"
              onClick={() => toggleSection('sms')}
            >
              <h3>SMS Settings</h3>
              {alertConfig.alertType === 'both' && (
                <span className="toggle-icon">
                  {expandedSections.sms ? '▼' : '▶'}
                </span>
              )}
            </div>
            <div className={`settings-content ${alertConfig.alertType === 'both' && !expandedSections.sms ? 'collapsed' : ''}`}>
              <div className="form-group">
                <label htmlFor="senderPhone">Sender Phone Number</label>
                <input
                  type="text"
                  id="senderPhone"
                  name="senderPhone"
                  value={alertConfig.sms.senderPhone}
                  onChange={handleSmsChange}
                  placeholder="+1234567890"
                  required={alertConfig.alertType === 'sms' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="gatewayUrl">SMS Gateway URL</label>
                <input
                  type="text"
                  id="gatewayUrl"
                  name="gatewayUrl"
                  value={alertConfig.sms.gatewayUrl}
                  onChange={handleSmsChange}
                  placeholder="https://sms-gateway.example.com/api/send"
                  required={alertConfig.alertType === 'sms' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="apiKey">API Key / Token</label>
                <input
                  type="password"
                  id="apiKey"
                  name="apiKey"
                  value={alertConfig.sms.apiKey}
                  onChange={handleSmsChange}
                  placeholder="••••••••"
                  required={alertConfig.alertType === 'sms' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="receiverPhones">Receiver Phone Numbers (Comma-separated)</label>
                <input
                  type="text"
                  id="receiverPhones"
                  name="receiverPhones"
                  value={alertConfig.sms.receiverPhones}
                  onChange={handleSmsChange}
                  placeholder="+1234567890, +0987654321"
                  required={alertConfig.alertType === 'sms' || alertConfig.alertType === 'both'}
                />
              </div>
              <div className="form-group">
                <label htmlFor="messageTemplate">Message Template</label>
                <textarea
                  id="messageTemplate"
                  name="messageTemplate"
                  value={alertConfig.sms.messageTemplate}
                  onChange={handleSmsChange}
                  placeholder="Alert: {event_type} detected at {location}. Time: {timestamp}"
                  required={alertConfig.alertType === 'sms' || alertConfig.alertType === 'both'}
                  rows={4}
                />
              </div>
              <div className="form-actions test-sms-action">
                <button
                  type="button"
                  className="test-button"
                  onClick={handleSendTestSms}
                >
                  Send Test SMS
                </button>
              </div>
            </div>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}
        {saveSuccess && <div className="success-message">Configuration saved successfully!</div>}

        <div className="form-actions">
          <button type="submit" className="save-button" disabled={saving}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default SenderConfiguration;
