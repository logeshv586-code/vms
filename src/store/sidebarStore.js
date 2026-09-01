import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * Centralized store for managing sidebar state across all modules
 * Features:
 * - Tracks expanded/collapsed state
 * - Tracks pinned/unpinned state
 * - Persists state across page refreshes and app restarts
 * - Provides consistent behavior across all sidebar instances
 */
export const useSidebarStore = create(
  persist(
    (set) => ({
      // Whether the sidebar is expanded (240px) or collapsed (60px)
      isExpanded: false,
      
      // Whether the sidebar is pinned in expanded state
      isPinned: false,
      
      // Set expanded state
      setExpanded: (expanded) => set({ isExpanded: expanded }),
      
      // Toggle expanded state
      toggleExpanded: () => set((state) => ({ isExpanded: !state.isExpanded })),
      
      // Set pinned state
      setPinned: (pinned) => set({ isPinned: pinned }),
      
      // Toggle pinned state
      togglePinned: () => set((state) => {
        const newPinnedState = !state.isPinned;
        // If pinning, ensure sidebar is expanded
        return { 
          isPinned: newPinnedState,
          isExpanded: newPinnedState ? true : state.isExpanded
        };
      }),
    }),
    {
      name: 'sidebar-storage', // localStorage key
      getStorage: () => localStorage,
    }
  )
);

export default useSidebarStore;
