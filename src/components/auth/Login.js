import React, { useState, useEffect } from 'react';
import { useUserStore } from '../../store/userStore';
import './Login.css';
// Import icons for the login form
import { FaUser, FaLock, FaUserShield } from 'react-icons/fa';

const Login = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('Admin');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
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
    <div className="login-container">
      <div className="login-background"></div>
      <div className="login-card">
        <div className="login-header">
          <img src="/assets/ESIL_LOGO.png" alt="ESIL Logo" className="login-logo" />
          <h2>Eagle VMS</h2>
          <p className="login-subtitle">VMS</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}

          <div className="form-group">
            <div className="input-icon-wrapper">
              <FaUser className="input-icon" />
              <input
                type="text"
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Username"
                required
                disabled={loading}
              />
            </div>
          </div>

          <div className="form-group">
            <div className="input-icon-wrapper">
              <FaLock className="input-icon" />
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                disabled={loading}
              />
              <button
                type="button"
                className="toggle-password"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>
          <div className="form-group">
            <div className="input-icon-wrapper">
              <FaUserShield className="input-icon" />
              <select
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="role-select"
                disabled={loading || username.toLowerCase() === 'eagleai'}
              >
                <option value="Admin">Admin</option>
                <option value="Supervisor">Supervisor</option>
              </select>
            </div>
          </div>



          <div className="form-options">
            <div className="remember-me">
              <input
                type="checkbox"
                id="rememberMe"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                disabled={loading}
              />
              <label htmlFor="rememberMe">Remember me</label>
            </div>
          </div>

          <button
            type="submit"
            className="login-button"
            disabled={loading}
          >
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>

        {/* Login footer removed */}
      </div>
    </div>
  );
};

export default Login;
