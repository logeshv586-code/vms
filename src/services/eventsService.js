// Compatibility shim. The canonical implementation lives in eventService.js.
export {
  eventService as default,
  eventService,
  getCurrentEvents,
  searchEvents,
  acknowledgeEvent,
  resolveEvent,
  fetchEventRules,
  updateEventRules,
  toggleDetectionRule,
  fetchEventStatistics,
  fetchCameraRules,
  applyCameraRules,
  toggleCameraRule
} from './eventService';
