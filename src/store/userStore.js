import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { API_BASE_URL } from '../utils/apiConfig';
import { apiRequest } from '../utils/api';

// Helper function to get the API URL for user management
const getUserApiUrl = (endpoint) => `${API_BASE_URL}/api/augment/users${endpoint ? `/${endpoint}` : ''}`;

export const useUserStore = create(
  persist(
    (set, get) => ({
      // User state
      currentUser: null,
      isAuthenticated: false,
      users: [],
      error: null,
      loading: false,

      // Login function
      login: async (username, password, role = null) => {
        set({ loading: true, error: null });
        try {
          // Call the backend API for authentication
          const response = await apiRequest(getUserApiUrl('login'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role })
          });

          if (response.success) {
            const userData = {
              ...response.data.user,
              server_boot_id: response.data.server_boot_id || response.data.user?.server_boot_id,
              access_token: response.data.access_token || response.data.user?.access_token,
              login_time: Date.now()
            };
            set({
              currentUser: userData,
              isAuthenticated: true,
              loading: false
            });
            return true;
          } else {
            set({ error: response.error || 'Login failed', loading: false });
            return false;
          }
        } catch (error) {
          console.error("Login error:", error);
          set({
            error: 'Connection error. Please try again later.',
            loading: false
          });
          return false;
        }
      },

      // Logout function
      logout: () => {
        set({
          currentUser: null,
          isAuthenticated: false
        });
      },

      // Check session validity against backend (forces password prompt on backend restart or after 8 hours)
      checkSession: async () => {
        const { currentUser, logout } = get();
        if (!currentUser) return false;

        // 1. Enforce 8-hour session expiration rule (8 hours = 8 * 60 * 60 * 1000 ms)
        const EIGHT_HOURS_MS = 8 * 60 * 60 * 1000;
        const now = Date.now();
        if (currentUser.login_time && (now - currentUser.login_time >= EIGHT_HOURS_MS)) {
          console.warn("8-hour session limit reached. Logout required.");
          logout();
          return false;
        }

        // 2. Enforce Backend Restart invalidation rule
        try {
          const bootId = currentUser.server_boot_id || '';
          const token = currentUser.access_token || '';
          const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

          const response = await apiRequest(getUserApiUrl(`verify-session?server_boot_id=${encodeURIComponent(bootId)}`), {
            method: 'GET',
            headers
          });

          if (response && response.valid === false) {
            console.warn("Backend server was restarted or session is invalid. Asking for password.");
            logout();
            return false;
          }
          return true;
        } catch (error) {
          console.debug("Transient session verification error (backend starting/unreachable):", error);
          return false;
        }
      },

      // Get all users (for SuperAdmin and Admin)
      getUsers: async () => {
        set({ loading: true, error: null });
        try {
          const response = await apiRequest(getUserApiUrl(), {
            method: 'GET'
          });

          if (response.success) {
            set({ users: response.data, loading: false });
          } else {
            set({ error: response.error || 'Failed to fetch users', loading: false });
          }
        } catch (error) {
          console.error("Error fetching users:", error);

          // Check if we already have users in the store
          const existingUsers = get().users || [];

          if (existingUsers.length > 0) {
            // If we already have users, keep them
            set({ loading: false });
          } else {
            // Set error if we have no users
            set({
              error: 'Failed to connect to server. Please try again later.',
              loading: false
            });
          }
        }
      },

      // Create a new user (SuperAdmin creates Admin, Admin creates Supervisor)
      createUser: async (userData) => {
        set({ loading: true, error: null });
        try {
          const response = await apiRequest(getUserApiUrl(), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
          });

          if (response.success) {
            set(state => ({
              users: [...state.users, response.data],
              loading: false
            }));
            return true;
          } else {
            set({ error: response.error || 'Failed to create user', loading: false });
            return false;
          }
        } catch (error) {
          console.error("Error creating user:", error);
          set({
            error: 'Connection error. Failed to create user. Please try again later.',
            loading: false
          });
          return false;
        }
      },

      // Update user permissions
      updateUserPermissions: async (userId, permissions) => {
        set({ loading: true, error: null });

        // Get current user information
        const { currentUser } = get();

        try {
          // Add current user information to the request URL as query parameters
          const queryParams = currentUser ?
            `?current_user_id=${currentUser.id}&current_user_role=${currentUser.role}` : '';

          console.log(`Sending permission update to: ${getUserApiUrl(`${userId}/permissions`) + queryParams}`);

          // Send the update to the backend and wait for the response
          const response = await apiRequest(getUserApiUrl(`${userId}/permissions`) + queryParams, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(permissions)
          });

          console.log('Permission update response:', response);

          if (response.success) {
            // Update the UI after successful backend update
            set(state => ({
              users: state.users.map(user =>
                user.id === userId
                  ? { ...user, permissions: permissions }
                  : user
              ),
              loading: false
            }));
            return true;
          } else {
            set({
              error: response.error || 'Failed to update permissions',
              loading: false
            });
            return false;
          }
        } catch (error) {
          console.error("Error in updateUserPermissions:", error);
          set({
            error: 'Connection error. Failed to update permissions. Please try again later.',
            loading: false
          });
          return false;
        }
      },

      // Delete a user
      deleteUser: async (userId) => {
        set({ loading: true, error: null });

        // Get current user information
        const { currentUser } = get();

        console.log(`Attempting to delete user with ID: ${userId}`);

        try {
          // Add current user information to the request URL as query parameters
          const queryParams = currentUser ?
            `?current_user_id=${currentUser.id}&current_user_role=${currentUser.role}&current_user_username=${currentUser.username}` : '';

          console.log(`Sending DELETE request to: ${getUserApiUrl(userId) + queryParams}`);

          const response = await apiRequest(getUserApiUrl(userId) + queryParams, {
            method: 'DELETE'
          });

          console.log(`Delete response:`, response);

          if (response.success) {
            // Update the local state only after successful backend deletion
            set(state => {
              console.log(`Removing user ${userId} from local state. Before: ${state.users.length} users`);
              const updatedUsers = state.users.filter(user => user.id !== userId);
              console.log(`After filtering: ${updatedUsers.length} users`);
              return {
                users: updatedUsers,
                loading: false
              };
            });

            // Refresh the users list from the backend to ensure sync
            setTimeout(async () => {
              try {
                console.log("Refreshing users list after deletion");
                const refreshResponse = await apiRequest(getUserApiUrl(), {
                  method: 'GET'
                });

                if (refreshResponse.success) {
                  set({
                    users: refreshResponse.data,
                    loading: false
                  });
                  console.log(`Users list refreshed. Now have ${refreshResponse.data.length} users`);
                }
              } catch (refreshError) {
                console.error("Error refreshing users after deletion:", refreshError);
              }
            }, 500); // Small delay to ensure backend has completed the operation

            return true;
          } else {
            console.error("Backend reported error during user deletion:", response.error);
            set({ error: response.error || 'Failed to delete user', loading: false });
            return false;
          }
        } catch (error) {
          console.error("Error deleting user:", error);
          set({
            error: 'Connection error. Failed to delete user. Please try again later.',
            loading: false
          });
          return false;
        }
      },

      // Check if user has a specific permission
      hasPermission: (permission) => {
        const { currentUser } = get();
        if (!currentUser) return false;

        // SuperAdmin always has all permissions
        if (currentUser.role === 'SuperAdmin') return true;

        // Check specific permission
        return currentUser.permissions && currentUser.permissions[permission] === true;
      }
    }),
    {
      name: 'user-storage',
      getStorage: () => sessionStorage,
      partialize: (state) => ({
        // Do NOT persist currentUser or isAuthenticated across page reloads or backend restarts!
        // Password login is required on page reload, backend restart, and after 8 hours.
        users: state.users
      })
    }
  )
);

// Clear legacy localStorage user-storage key to ensure clean login requirement
try {
  if (typeof window !== 'undefined' && window.localStorage) {
    window.localStorage.removeItem('user-storage');
  }
} catch (e) {
  // Ignore
}
