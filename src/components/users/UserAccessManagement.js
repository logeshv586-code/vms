import React, { useState, useEffect } from 'react';
import { useUserStore } from '../../store/userStore';
import './UserAccessManagement.css';
import addIcon from '../../icon/add-icon.png';
import UserRolesTable from './UserRolesTable';

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

const UserAccessManagement = () => {
  const {
    currentUser,
    users,
    getUsers,
    createUser,
    updateUserPermissions,
    deleteUser,
    loading,
    error
  } = useUserStore();

  const [showAddUserForm, setShowAddUserForm] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [formError, setFormError] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  // Define all available permissions
  const allPermissions = [
    { id: 'searchEvents', label: 'Search Events' },
    { id: 'currentEvents', label: 'Current Events' },
    { id: 'setDetection', label: 'Set Detection' },
    { id: 'eventStatistics', label: 'Event Statistics' },
    { id: 'currentRecordings', label: 'Current Recordings' },
    { id: 'archivePlayback', label: 'Archive Playback' },
    { id: 'recordingReport', label: 'Recording Report' },
    { id: 'criticalVideo', label: 'Critical Video' },
    { id: 'redundantPlayback', label: 'Redundant Playback' },
    { id: 'drSites', label: 'DR Sites' }
  ];

  // Load users on component mount and set up periodic refresh
  useEffect(() => {
    console.log("Loading users in UserAccessManagement");
    getUsers();

    // Set up periodic refresh to ensure frontend stays in sync with backend
    const refreshInterval = setInterval(() => {
      console.log("Performing periodic refresh of users");
      getUsers();
    }, 30000); // Refresh every 30 seconds

    // Clean up interval on component unmount
    return () => clearInterval(refreshInterval);
  }, [getUsers]);

  // Log users whenever they change
  useEffect(() => {
    console.log("Users in UserAccessManagement:", users);
  }, [users]);

  // Initialize user logs if needed
  useEffect(() => {
    // We no longer add a system initialization log entry
    // This space is kept for future initialization if needed
  }, []);

  // Filter users based on current user's role
  const filteredUsers = users.filter(user => {
    if (currentUser.role === 'SuperAdmin') {
      // SuperAdmin sees all users except themselves
      return user.id !== currentUser.id;
    } else if (currentUser.role === 'Admin') {
      // Admin sees only Supervisors they created
      // Check if the supervisor's username starts with the admin's username followed by a dash
      return user.role === 'Supervisor' &&
             user.username.startsWith(`${currentUser.username}-`) &&
             user.created_by === currentUser.username;
    }
    return false;
  });

  // Handle adding a new user
  const handleAddUser = async (e) => {
    e.preventDefault();
    setFormError('');
    setPasswordError('');

    if (!newUsername.trim()) {
      setFormError('Username is required');
      return;
    }

    if (!newPassword.trim()) {
      setFormError('Password is required');
      return;
    }

    // Determine role based on current user
    const role = currentUser.role === 'SuperAdmin' ? 'Admin' : 'Supervisor';

    // Password validation for Admin and Supervisor users
    // Not required for SuperAdmin (but SuperAdmin can't be created through the UI anyway)
    if (role === 'Admin' || role === 'Supervisor') {
      const passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$/;

      if (!passwordPattern.test(newPassword)) {
        setPasswordError('Password must be at least 8 characters long and include uppercase, lowercase, number, and special character.');
        return;
      } else {
        // Clear password error if validation passes
        setPasswordError('');
      }
    }

    // Create default permissions based on current user's permissions
    // Admin can only grant permissions they have
    const permissions = {};
    allPermissions.forEach(permission => {
      if (currentUser.role === 'SuperAdmin') {
        // SuperAdmin can grant any permission to Admin
        permissions[permission.id] = false;
      } else {
        // Admin can only grant permissions they have
        permissions[permission.id] = currentUser.permissions[permission.id] ? false : false;
      }
    });

    // If Admin, they cannot grant manageUser permission to Supervisor
    if (currentUser.role === 'Admin') {
      permissions.manageUser = false;
    }

    // For Admin users creating Supervisors, prefix the username with the admin's username
    const finalUsername = currentUser.role === 'Admin'
      ? `${currentUser.username}-${newUsername}`
      : newUsername;

    const userData = {
      username: finalUsername,
      password: newPassword,
      role,
      permissions,
      created_by: currentUser.username
    };

    const success = await createUser(userData);
    if (success) {
      // Find the newly created user in the updated users list
      const createdUser = users.find(u => u.username === finalUsername && u.role === role);
      if (createdUser) {
        setNewlyCreatedUser(createdUser.id);

        // Add log entry
        addLogEntry('CREATE_USER', {
          username: finalUsername,
          role: role,
          userId: createdUser.id
        });

        // Scroll to the appropriate section after a short delay to allow rendering
        setTimeout(() => {
          if (role === 'Admin' && adminSectionRef.current) {
            adminSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
          } else if (role === 'Supervisor' && supervisorSectionRef.current) {
            supervisorSectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
          }
        }, 100);

        // Clear the newly created user highlight after 3 seconds
        setTimeout(() => {
          setNewlyCreatedUser(null);
        }, 3000);
      }

      setNewUsername('');
      setNewPassword('');
      setPasswordError('');
      setShowAddUserForm(false);
    }
  };

  // We no longer need to track updating permissions since updates are immediate
  const [newlyCreatedUser, setNewlyCreatedUser] = useState(null);
  const [activeTab, setActiveTab] = useState('access'); // 'access', 'all-users', 'logs', 'role-tables'
  const [userLogs, setUserLogs] = useState([]);

  // Refs for scrolling to newly created users
  const adminSectionRef = React.useRef(null);
  const supervisorSectionRef = React.useRef(null);

  // Handle permission change
  const handlePermissionChange = async (userId, permissionId, checked) => {
    const user = users.find(u => u.id === userId);
    if (!user) return;

    // Additional validation to ensure Admin can only grant permissions they have
    if (currentUser.role === 'Admin' && checked) {
      // Check if Admin is trying to grant a permission they don't have
      if (!currentUser.permissions[permissionId]) {
        console.error(`Admin ${currentUser.username} attempted to grant permission ${permissionId} they don't have`);
        // Refresh the users list to reset the UI
        getUsers();
        return;
      }

      // Special case: Admin can't grant manageUser permission to Supervisors
      if (permissionId === 'manageUser' && user.role === 'Supervisor') {
        console.error(`Admin ${currentUser.username} attempted to grant manageUser permission to Supervisor ${user.username}`);
        // Refresh the users list to reset the UI
        getUsers();
        return;
      }
    }

    // Create a copy of the user's permissions
    const updatedPermissions = {
      ...user.permissions,
      [permissionId]: checked
    };

    console.log(`Updating permissions for ${user.username}: ${permissionId} = ${checked}`);

    // Update permissions and wait for the result
    const success = await updateUserPermissions(userId, updatedPermissions);

    if (success) {
      // Add log entry only if update was successful
      addLogEntry('UPDATE_PERMISSION', {
        username: user.username,
        role: user.role,
        userId: userId,
        permission: permissionId,
        value: checked
      });
      console.log(`Successfully updated permission ${permissionId} to ${checked} for ${user.username}`);
    } else {
      console.error(`Failed to update permission ${permissionId} for ${user.username}`);
      // Refresh the users list to reset the UI
      getUsers();
    }
  };

  // Handle user deletion
  const handleDeleteUser = async () => {
    if (selectedUser) {
      console.log(`Handling deletion of user ID: ${selectedUser}`);

      // If we're deleting the newly created user, clear that state
      if (newlyCreatedUser === selectedUser) {
        setNewlyCreatedUser(null);
      }

      // Get user details before deletion for the log
      const userToDelete = users.find(u => u.id === selectedUser);

      if (!userToDelete) {
        console.error(`User with ID ${selectedUser} not found in local state`);
        setDeleteError('User not found');
        setSelectedUser(null);
        setShowDeleteConfirm(false);
        return;
      }

      console.log(`Found user to delete: ${userToDelete.username} (ID: ${userToDelete.id}, Role: ${userToDelete.role})`);

      // Check if current user can delete this user
      if (!canDeleteUser(currentUser, userToDelete)) {
        console.warn(`User ${currentUser.username} does not have permission to delete ${userToDelete.username}`);
        setDeleteError('You do not have permission to delete this user');
        setSelectedUser(null);
        setShowDeleteConfirm(false);
        return;
      }

      console.log(`Calling deleteUser API for user ID: ${selectedUser}`);
      const success = await deleteUser(selectedUser);
      console.log(`Delete API call result: ${success ? 'Success' : 'Failed'}`);

      if (success) {
        // Add log entry
        addLogEntry('DELETE_USER', {
          username: userToDelete.username,
          role: userToDelete.role,
          userId: selectedUser
        });

        console.log(`Added log entry for deletion of ${userToDelete.username}`);

        // Force refresh users list to ensure UI is in sync with backend
        setTimeout(() => {
          console.log("Refreshing users list after deletion");
          getUsers();
        }, 1000);
      } else {
        console.error(`Failed to delete user ${userToDelete.username}`);
      }

      setSelectedUser(null);
      setShowDeleteConfirm(false);
    }
  };

  // Check if current user can modify a specific permission
  const canModifyPermission = (permissionId) => {
    // SuperAdmin can modify all permissions
    if (currentUser.role === 'SuperAdmin') return true;

    // Admin can only modify permissions they have
    return currentUser.permissions[permissionId] === true;
  };

  // Filter permissions based on current user's access
  // SuperAdmin sees all permissions
  // Admin sees only permissions granted to them by SuperAdmin
  // Supervisor sees only permissions granted to them by their Admin
  const accessiblePermissions = allPermissions.filter(permission => {
    if (currentUser.role === 'SuperAdmin') {
      // SuperAdmin sees all permissions
      return true;
    }
    // For Admin and Supervisor, only show permissions they have been granted
    return currentUser.permissions && currentUser.permissions[permission.id] === true;
  });

  // Add a log entry
  const addLogEntry = (action, details) => {
    const newLog = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      user: currentUser.username,
      userRole: currentUser.role,
      action,
      details
    };

    setUserLogs(prevLogs => [newLog, ...prevLogs]);
  };

  return (
    <div className="user-access-management">
      <div className="user-access-header">
        <h2>User Management</h2>
        <button
          className="add-user-button"
          onClick={() => setShowAddUserForm(true)}
        >
          <img src={addIcon} alt="Add" className="add-icon" />
          Add {currentUser.role === 'SuperAdmin' ? 'Admin' : 'Supervisor'}
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="user-tabs"  >
        <button style={{color: '#000000'}}
          className={`tab-button ${activeTab === 'access' ? 'active' : ''}`}
          onClick={() => setActiveTab('access')}
        >
          User Access Levels
        </button>
        <button style={{color: '#000000'}}
          className={`tab-button ${activeTab === 'all-users' ? 'active' : ''} ` }
          onClick={() => setActiveTab('all-users')}
        >
          All Users
        </button>
        <button style={{color: '#000000'}}
          className={`tab-button ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          User Logs
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Add User Form */}
      {showAddUserForm && (
        <div className="add-user-form-container">
          <form onSubmit={handleAddUser} className="add-user-form">
            <h3>Add New {currentUser.role === 'SuperAdmin' ? 'Admin' : 'Supervisor'}</h3>

            {formError && <div className="form-error">{formError}</div>}
            {passwordError && <div className="form-error">{passwordError}</div>}

            <div className="form-group">
              <label htmlFor="username">Username</label>
              {currentUser.role === 'Admin' ? (
                <div className="username-input-group">
                  <div className="username-prefix">{currentUser.username}-</div>
                  <input
                    type="text"
                    id="username"
                    value={newUsername}
                    onChange={(e) => setNewUsername(e.target.value)}
                    placeholder="Enter supervisor name"
                    required
                    className="username-with-prefix"
                  />
                </div>
              ) : (
                <input
                  type="text"
                  id="username"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Enter username"
                  required
                />
              )}
            </div>

            <div className="form-group">
              <label htmlFor="password">Password</label>
              <input
                type="password"
                id="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
              {passwordError && (
                <div className="password-requirements">
                  <p>Password requirements for {currentUser.role === 'SuperAdmin' ? 'Admin' : 'Supervisor'} users:</p>
                  <ul>
                    <li>At least 8 characters</li>
                    <li>At least one uppercase letter</li>
                    <li>At least one lowercase letter</li>
                    <li>At least one number</li>
                    <li>At least one special character (!@#$%^&*)</li>
                  </ul>
                </div>
              )}
            </div>

            <div className="form-actions">
              <button type="submit" className="save-button" disabled={loading}>
                {loading ? 'Adding...' : 'Add User'}
              </button>
              <button
                type="button"
                className="cancel-button"
                onClick={() => {
                  setShowAddUserForm(false);
                  setFormError('');
                  setPasswordError('');
                  setNewUsername('');
                  setNewPassword('');
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tab Content */}
      {activeTab === 'access' && (
        <>
          {/* User Access Table */}
          <div className="user-access-table-container">
            <table className="user-access-table">
              <thead>
                <tr>
                  <th className="service-column">Service</th>
                  {filteredUsers.map(user => (
                    <th key={user.id} className="user-column">
                      <div className="user-column-header">
                        <div className="user-info-header">
                          <span className="username-header">{user.username}</span>
                          <span className={`role-badge-small ${user.role.toLowerCase()}`}>{user.role}</span>
                        </div>
                        {canDeleteUser(currentUser, user) && (
                          <button
                            className="delete-user-button"
                            onClick={() => {
                              setSelectedUser(user.id);
                              setShowDeleteConfirm(true);
                            }}
                            title={`Delete ${user.username}`}
                          >
                            ×
                          </button>
                        )}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {accessiblePermissions.map(permission => (
                  <tr key={permission.id}>
                    <td className="service-name">{permission.label}</td>

                    {/* Other users' permissions */}
                    {filteredUsers.map(user => {
                      const isDisabled =
                        // Admin can't modify manageUser for Supervisors
                        (currentUser.role === 'Admin' && permission.id === 'manageUser') ||
                        // Can only grant permissions the current user has
                        !canModifyPermission(permission.id);

                      return (
                        <td key={user.id} className="permission-cell">
                          <label
                            className="checkbox-container"
                            title={isDisabled ? 'Permission cannot be modified' : `${user.permissions[permission.id] ? 'Remove' : 'Grant'} ${permission.label} permission`}
                          >
                            <input
                              type="checkbox"
                              checked={user.permissions[permission.id] || false}
                              onChange={(e) => handlePermissionChange(user.id, permission.id, e.target.checked)}
                              disabled={isDisabled}
                            />
                            <span className="checkmark"></span>
                          </label>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {activeTab === 'all-users' && (
        <div className="all-users-section">
          <h3>All Users</h3>
          <p className="section-description">
            This view shows all users organized by their roles, with their respective permissions and access levels.
          </p>

          <UserRolesTable
            users={users}
            currentUser={currentUser}
            allPermissions={allPermissions}
            newlyCreatedUser={newlyCreatedUser}
            onDeleteUser={(userId) => {
              setSelectedUser(userId);
              setShowDeleteConfirm(true);
            }}
          />
        </div>
      )}

      {activeTab === 'logs' && (
        <div className="user-logs-section">
          <h3>User Activity Logs</h3>

          <div className="logs-container">
            {userLogs.length > 0 ? (
              <table className="logs-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>User</th>
                    <th>Role</th>
                    <th>Action</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {userLogs.map(log => (
                    <tr key={log.id} className="log-entry">
                      <td className="log-timestamp">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="log-user">{log.user}</td>
                      <td className="log-role">
                        <span className={`role-badge-small ${log.userRole.toLowerCase()}`}>
                          {log.userRole}
                        </span>
                      </td>
                      <td className="log-action">
                        <span className={`action-badge ${log.action.toLowerCase()}`}>
                          {log.action.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="log-details">
                        {log.action === 'CREATE_USER' && (
                          <span>Created {log.details.role} user: {log.details.username}</span>
                        )}
                        {log.action === 'UPDATE_PERMISSION' && (
                          <span>
                            {log.details.value ? 'Granted' : 'Removed'} permission "{allPermissions.find(p => p.id === log.details.permission)?.label}"
                            for {log.details.username} ({log.details.role})
                          </span>
                        )}
                        {log.action === 'DELETE_USER' && (
                          <span>Deleted {log.details.role} user: {log.details.username}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="no-logs-message">
                No user activity logs available yet. Actions like creating users, updating permissions, or deleting users will be recorded here.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Delete User</h3>
            {deleteError && <div className="error-message">{deleteError}</div>}
            <p>Are you sure you want to delete this user? This action cannot be undone.</p>
            <div className="modal-actions">
              <button
                className="confirm-button"
                onClick={handleDeleteUser}
                disabled={loading}
              >
                {loading ? 'Deleting...' : 'Delete'}
              </button>
              <button
                className="cancel-button"
                onClick={() => {
                  setDeleteError('');
                  setShowDeleteConfirm(false);
                  setSelectedUser(null);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserAccessManagement;
