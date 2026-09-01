import React, { useState } from 'react';
import './UserAccessManagement.css';

// Password display component with show/hide toggle
const PasswordDisplay = ({ password }) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="password-display">
      <span className="password-value">
        {showPassword ? password : '••••••••'}
      </span>
      <button
        className="password-toggle"
        onClick={() => setShowPassword(!showPassword)}
        title={showPassword ? "Hide password" : "Show password"}
      >
        {showPassword ? '🔒' : '👁️'}
      </button>
    </div>
  );
};

const UserRolesTable = ({ users, currentUser, allPermissions, onDeleteUser, newlyCreatedUser }) => {
  // Group users by role
  // For SuperAdmin: show all users
  // For Admin: only show their own Supervisors (no SuperAdmin, no other Admins)
  const superAdmins = users.filter(user => {
    if (currentUser.role === 'SuperAdmin') {
      return user.role === 'SuperAdmin';
    }
    // Admin should not see SuperAdmin
    return false;
  });
  
  const admins = users.filter(user => {
    if (currentUser.role === 'SuperAdmin') {
      return user.role === 'Admin';
    }
    // Admin should not see other Admins
    return false;
  });
  
  const supervisors = users.filter(user => {
    // For SuperAdmin, show all supervisors
    if (currentUser.role === 'SuperAdmin') {
      return user.role === 'Supervisor';
    }
    // For Admin, only show supervisors they created
    else if (currentUser.role === 'Admin') {
      return user.role === 'Supervisor' &&
             user.username.startsWith(`${currentUser.username}-`) &&
             user.created_by === currentUser.username;
    }
    return false;
  });

  // Helper function to determine if current user can delete a target user
  const canDeleteUser = (currentUser, targetUser) => {
    // Cannot delete self
    if (currentUser.id === targetUser.id) return false;

    // SuperAdmin can delete any Admin or Supervisor, but not other SuperAdmins
    if (currentUser.role === 'SuperAdmin') {
      return targetUser.role !== 'SuperAdmin';
    }

    // Admin can only delete Supervisors they created
    if (currentUser.role === 'Admin') {
      return targetUser.role === 'Supervisor' && targetUser.created_by === currentUser.username;
    }

    // Supervisors cannot delete anyone
    return false;
  };

  return (
    <div className="user-roles-table-container">
      {/* SuperAdmin Table */}
      {superAdmins.length > 0 && (
        <div className="role-table-section">
          <h3 className="role-table-title">
            SuperAdmin
            <span className="role-badge superadmin">Full Access</span>
          </h3>
          <table className="role-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Username</th>
                <th>Status</th>
                <th>Password</th>
                <th>Permissions</th>
              </tr>
            </thead>
            <tbody>
              {superAdmins.map(user => (
                <tr key={user.id} className="role-table-row superadmin-row">
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td><span className="status-badge active">Active</span></td>
                  <td>
                    {currentUser.role === 'SuperAdmin' && (
                      <PasswordDisplay password={user.password} />
                    )}
                  </td>
                  <td className="permissions-cell">
                    <div className="permissions-list-table">
                      {Object.entries(user.permissions)
                        .filter(([_, value]) => value)
                        .map(([key]) => (
                          <span key={key} className="permission-tag active">
                            {allPermissions.find(p => p.id === key)?.label || key}
                          </span>
                        ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Admin Table */}
      {admins.length > 0 && (
        <div className="role-table-section">
          <h3 className="role-table-title">
            Admin
            <span className="role-badge admin">Controlled Access</span>
          </h3>
          <table className="role-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Username</th>
                <th>Status</th>
                <th>Password</th>
                <th>Permissions</th>
                {currentUser.role === 'SuperAdmin' && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {admins.map(user => (
                <tr key={user.id} className={`role-table-row admin-row ${newlyCreatedUser === user.id ? 'newly-created' : ''}`}>
                  <td>{user.id}</td>
                  <td>
                    {user.username}
                    {newlyCreatedUser === user.id && <span className="new-badge">New</span>}
                  </td>
                  <td><span className="status-badge active">Active</span></td>
                  <td>
                    {currentUser.role === 'SuperAdmin' && (
                      <PasswordDisplay password={user.password} />
                    )}
                  </td>
                  <td className="permissions-cell">
                    <div className="permissions-list-table">
                      {Object.entries(user.permissions)
                        .filter(([_, value]) => value)
                        .map(([key]) => (
                          <span key={key} className="permission-tag active">
                            {allPermissions.find(p => p.id === key)?.label || key}
                          </span>
                        ))}
                    </div>
                  </td>
                  {currentUser.role === 'SuperAdmin' && (
                    <td>
                      {canDeleteUser(currentUser, user) && (
                        <button
                          className="table-action-button delete"
                          onClick={() => onDeleteUser(user.id)}
                          title={`Delete ${user.username}`}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Supervisor Table */}
      {supervisors.length > 0 && (
        <div className="role-table-section">
          <h3 className="role-table-title">
            Supervisor
            <span className="role-badge supervisor">Limited Access</span>
          </h3>
          <table className="role-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Username</th>
                <th>Status</th>
                <th>Password</th>
                <th>Permissions</th>
                {(currentUser.role === 'SuperAdmin' || currentUser.role === 'Admin') && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {supervisors.map(user => (
                <tr key={user.id} className={`role-table-row supervisor-row ${newlyCreatedUser === user.id ? 'newly-created' : ''}`}>
                  <td>{user.id}</td>
                  <td>
                    {user.username}
                    {newlyCreatedUser === user.id && <span className="new-badge">New</span>}
                  </td>
                  <td><span className="status-badge active">Active</span></td>
                  <td>
                    {currentUser.role === 'SuperAdmin' && (
                      <PasswordDisplay password={user.password} />
                    )}
                  </td>
                  <td className="permissions-cell">
                    <div className="permissions-list-table">
                      {Object.entries(user.permissions)
                        .filter(([_, value]) => value)
                        .map(([key]) => (
                          <span key={key} className="permission-tag active">
                            {allPermissions.find(p => p.id === key)?.label || key}
                          </span>
                        ))}
                    </div>
                  </td>
                  {(currentUser.role === 'SuperAdmin' || currentUser.role === 'Admin') && (
                    <td>
                      {canDeleteUser(currentUser, user) && (
                        <button
                          className="table-action-button delete"
                          onClick={() => onDeleteUser(user.id)}
                          title={`Delete ${user.username}`}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {users.length === 0 && (
        <div className="no-users-message">
          No users have been created yet.
        </div>
      )}
    </div>
  );
};

export default UserRolesTable;
