import { API_BASE_URL } from '../utils/apiConfig';

const EVENTS_API_URL = `${API_BASE_URL}/api/augment/events`;

export const eventService = {
  async getCurrentEvents() {
    try {
      const response = await fetch(`${EVENTS_API_URL}/current`);
      if (!response.ok) throw new Error('Failed to fetch current events');
      const data = await response.json();
      return data.success ? data.data : [];
    } catch (error) {
      console.error('Error fetching current events:', error);
      return [];
    }
  },

  async searchEvents(filters) {
    try {
      // Build query string from filters
      const queryParams = new URLSearchParams();
      Object.keys(filters).forEach(key => {
        if (filters[key] && filters[key] !== 'all' && filters[key] !== 'All Categories' && filters[key] !== 'All Rules' && filters[key] !== 'All Priorities' && filters[key] !== 'All Statuses' && filters[key] !== 'All Locations') {
          queryParams.append(key, filters[key]);
        }
      });
      
      const response = await fetch(`${EVENTS_API_URL}/search?${queryParams.toString()}`);
      if (!response.ok) throw new Error('Failed to search events');
      const data = await response.json();
      return data.success ? data.data : [];
    } catch (error) {
      console.error('Error searching events:', error);
      return [];
    }
  },

  async acknowledgeEvent(eventId) {
    try {
      const response = await fetch(`${EVENTS_API_URL}/acknowledge/${eventId}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to acknowledge event');
      const data = await response.json();
      return data.success;
    } catch (error) {
      console.error('Error acknowledging event:', error);
      return false;
    }
  },

  async resolveEvent(eventId) {
    try {
      const response = await fetch(`${EVENTS_API_URL}/resolve/${eventId}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to resolve event');
      const data = await response.json();
      return data.success;
    } catch (error) {
      console.error('Error resolving event:', error);
      return false;
    }
  }
};
