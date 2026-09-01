# Eagle VMS Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: Security updates |

## Security Architecture

Eagle VMS implements the following security controls:

- **Authentication**: JWT-based authentication with bcrypt password hashing
- **Authorization**: Role-based access control (SuperAdmin, Admin, Supervisor)
- **Session Management**: In-memory token storage with 8-hour access / 24-hour refresh tokens
- **Rate Limiting**: 5 failed login attempts trigger a 15-minute account lockout
- **Credential Protection**: Camera RTSP credentials encrypted at rest with AES-256-GCM
- **Input Validation**: Path traversal protection, RTSP URL validation, filename sanitization
- **Electron Security**: Context isolation enabled (`contextIsolation: true`), Node.js integration disabled in renderer (`nodeIntegration: false`), and IPC channels sandboxed via `preload.js` contextBridge
- **Audit Logging**: All security-relevant events logged to structured audit log

## Reporting a Vulnerability

If you discover a security vulnerability in Eagle VMS:

1. **Do NOT** open a public GitHub issue
2. Email security details to: security@eagleai.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
4. You will receive an acknowledgment within 48 hours
5. We aim to provide a fix within 7 business days for critical issues

## Security Best Practices for Deployment

- Change the default SuperAdmin password immediately after installation
- Use strong, unique passwords for all user accounts
- Keep the `.env` file secure and never commit it to version control
- Regularly review audit logs at `backend/logs/audit.log`
- Keep all dependencies updated
- If exposing the backend over a network, enable HTTPS/TLS
- Restrict network access to the VMS backend to trusted hosts only

## Credential Management

- Camera RTSP credentials are encrypted at rest using AES-256-GCM
- User passwords are hashed with bcrypt (cost factor 12)
- JWT tokens are signed with HS256 using a randomly generated secret key
- All credentials are stored server-side; the frontend never handles raw credentials

## Session Security

- Access tokens expire after 8 hours
- Refresh tokens expire after 24 hours
- Tokens are stored in memory only (never in localStorage or cookies)
- Token revocation is immediate on logout, password change, or permission changes
- Refresh token rotation is enabled (old tokens are invalidated on refresh)
