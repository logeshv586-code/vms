import React, { useState, useEffect } from 'react';
import { useUserStore } from '../../store/userStore';
import './ModernLogin.css';
import { FaUser, FaLock, FaUserShield } from 'react-icons/fa';

const ModernLogin = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('Admin');
  const [rememberMe, setRememberMe] = useState(false);
  const { login, error, loading, isAuthenticated } = useUserStore();

  useEffect(() => {
    // If already authenticated, call the success handler
    if (isAuthenticated) {
      onLoginSuccess();
    }
  }, [isAuthenticated, onLoginSuccess]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!username.trim() || !password.trim()) {
      return;
    }

    // If username is 'eagleAI', use SuperAdmin role automatically
    const loginRole = username.toLowerCase() === 'eagleai' ? 'SuperAdmin' : role;

    const success = await login(username, password, loginRole);
    if (success) {
      onLoginSuccess();
    }
  };

  return (
    <div className="container">
      <div className="forms-container">
        <div className="signin-signup">
          <form onSubmit={handleSubmit} className="sign-in-form">
            <img src="/assets/ESIL_LOGO.png" alt="Eagle Software Logo" className="logo" />
            <h2 className="title">Eagle VMS Login</h2>
            
            {error && <div className="error-message">{error}</div>}
            
            <div className="input-field">
              <i><FaUser /></i>
              <input 
                type="text" 
                placeholder="Username" 
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={loading}
                required 
              />
            </div>
            
            <div className="input-field">
              <i><FaLock /></i>
              <input 
                type="password" 
                placeholder="Password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                required 
              />
            </div>
            
            <div className="input-field">
              <i><FaUserShield /></i>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={loading || username.toLowerCase() === 'eagleai'}
              >
                <option value="Admin">Admin</option>
                <option value="Supervisor">Supervisor</option>
              </select>
            </div>
            
            <div className="checkbox-container">
              <input 
                type="checkbox" 
                id="rememberMe"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                disabled={loading}
              />
              <label htmlFor="rememberMe">Remember me</label>
            </div>
            
            <button type="submit" className="btn" disabled={loading}>
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
        </div>
      </div>

      <div className="panels-container">
        <div className="panel left-panel">
          <div className="content">
            <h3>Video Management System</h3>
            <p>
              Welcome to Eagle VMS, your comprehensive solution for video surveillance and management.
              Login to access your dashboard and manage your security system.
            </p>
          </div>
          <img src="/assets/login.svg" className="image" alt="Login" />
        </div>
      </div>
    </div>
  );
};

export default ModernLogin;
