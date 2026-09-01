import React, { useState, useEffect, useRef } from 'react';
import { useUserStore } from '../../store/userStore';
import './NewLogin.css';
import { FaUser, FaLock, FaUserShield } from 'react-icons/fa';
import { initializeLoginAnimation } from './loginAnimation';

const NewLogin = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('Admin');
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isSignup, setIsSignup] = useState(false);
  const { login, error, loading, isAuthenticated } = useUserStore();
  const canvasRef = useRef(null);

  useEffect(() => {
    // If already authenticated, call the success handler
    if (isAuthenticated) {
      onLoginSuccess();
    }
  }, [isAuthenticated, onLoginSuccess]);

  useEffect(() => {
    // Initialize canvas animations
    const cleanup = initializeLoginAnimation(canvasRef);

    return cleanup;
  }, []);

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

  const goRight = () => {
    setIsSignup(false);
    const slideBox = document.getElementById('slideBox');
    const topLayer = document.querySelector('.topLayer');

    if (slideBox && topLayer) {
      slideBox.style.marginLeft = '0';
      topLayer.style.marginLeft = '100%';
    }
  };

  const goLeft = () => {
    setIsSignup(true);
    const slideBox = document.getElementById('slideBox');
    const topLayer = document.querySelector('.topLayer');

    if (slideBox && topLayer) {
      if (window.innerWidth > 769) {
        slideBox.style.marginLeft = '50%';
      } else {
        slideBox.style.marginLeft = '20%';
      }
      topLayer.style.marginLeft = '0';
    }
  };

  return (
    <div className="login-container">
      <div id="back">
        <canvas ref={canvasRef} id="canvas" className="canvas-back"></canvas>
        <div className="backRight"></div>
        <div className="backLeft"></div>
      </div>

      <div id="slideBox">
        <div className="topLayer">
          <div className="left">
            <div className="content">
              <h2>Sign Up</h2>
              <div className="form-element form-stack">
                <label htmlFor="signup-username" className="form-label">Username</label>
                <input id="signup-username" type="text" name="username" />
              </div>
              <div className="form-element form-stack">
                <label htmlFor="signup-password" className="form-label">Password</label>
                <input id="signup-password" type="password" name="password" />
              </div>
              <div className="form-element form-stack">
                <label htmlFor="signup-email" className="form-label">Email</label>
                <input id="signup-email" type="email" name="email" />
              </div>
              <div className="form-element form-checkbox">
                <input className="checkbox" type="checkbox" id="signup-terms" />
                <label htmlFor="signup-terms">I agree to the Terms of Service</label>
              </div>
              <div className="form-element form-submit">
                <button id="signUp" className="signup" type="button" onClick={goRight}>Sign Up</button>
                <button id="goRight" className="off signup" type="button" onClick={goRight}>Log In</button>
              </div>
            </div>
          </div>
          <div className="right">
            <div className="content">
              <h2>Eagle VMS</h2>
              <img src="/assets/ESIL_LOGO.png" alt="ESIL Logo" className="login-logo" />

              <form onSubmit={handleSubmit}>
                {error && <div className="login-error">{error}</div>}

                <div className="form-element form-stack">
                  <label htmlFor="username" className="form-label">Username</label>
                  <input
                    id="username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    disabled={loading}
                  />
                </div>

                <div className="form-element form-stack">
                  <label htmlFor="password" className="form-label">Password</label>
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                  />
                </div>

                <div className="form-element form-stack">
                  <label htmlFor="role" className="form-label">Role</label>
                  <select
                    id="role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    disabled={loading || username.toLowerCase() === 'eagleai'}
                    style={{
                      backgroundColor: 'transparent',
                      border: '0',
                      borderBottom: '1px solid var(--theme-dark)',
                      outline: '0',
                      fontSize: '1em',
                      padding: '8px 1px',
                      marginTop: '0.1em',
                      width: '100%'
                    }}
                  >
                    <option value="Admin">Admin</option>
                    <option value="Supervisor">Supervisor</option>
                  </select>
                </div>

                <div className="form-element form-checkbox">
                  <input
                    className="checkbox"
                    type="checkbox"
                    id="rememberMe"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                    disabled={loading}
                  />
                  <label htmlFor="rememberMe">Remember me</label>
                </div>

                <div className="form-element form-submit">
                  <button
                    id="logIn"
                    className="login"
                    type="submit"
                    disabled={loading}
                  >
                    {loading ? "Logging in..." : "Log In"}
                  </button>
                  <button id="goLeft" className="off login" type="button" onClick={goLeft}>Sign Up</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewLogin;
