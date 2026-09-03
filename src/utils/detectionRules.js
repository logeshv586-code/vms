import { getCameraStreamId } from './cameraUtils';

export const DETECTION_RULES = [
  { id: 1, name: 'Appearance Search', category: 'Face Analytics', color: '#6366f1' },
  { id: 2, name: 'Camera Tamper', category: 'Security Analytics', color: '#ef4444' },
  { id: 3, name: 'Chain/Handbag Snatching', category: 'Crime Detection', color: '#d946ef' },
  { id: 4, name: 'Crowd Detection', category: 'Crowd & Public Safety', color: '#0f766e' },
  { id: 5, name: 'Eve Teasing', category: 'Crime Detection', color: '#f97316' },
  { id: 6, name: 'Face Capture', category: 'Face Analytics', color: '#10b981' },
  { id: 7, name: 'Face Recognition', category: 'Face Analytics', color: '#2563eb' },
  { id: 8, name: 'Gesture Detection', category: 'Crowd & Public Safety', color: '#8b5cf6' },
  { id: 9, name: 'Graffiti and Vandalism Detection', category: 'Crime Detection', color: '#f43f5e' },
  { id: 10, name: 'Intrusion Detection', category: 'Security Analytics', color: '#dc2626' },
  { id: 11, name: 'Lakshmanrekha Crossing', category: 'Security Analytics', color: '#ea580c' },
  { id: 12, name: 'Loitering', category: 'Security Analytics', color: '#a21caf' },
  { id: 13, name: 'Mobile Snatching', category: 'Crime Detection', color: '#6d28d9' },
  { id: 14, name: 'Object Classification', category: 'Security Analytics', color: '#64748b' },
  { id: 15, name: 'People Fighting', category: 'Crime Detection', color: '#e11d48' },
  { id: 16, name: 'Person Collapsing', category: 'Crowd & Public Safety', color: '#06b6d4' },
  { id: 17, name: 'Strike / Morcha / Hartal / Procession', category: 'Crowd & Public Safety', color: '#b45309' },
  { id: 18, name: 'Suspected Appearance', category: 'Face Analytics', color: '#701a75' },
  { id: 19, name: 'Unattended Object', category: 'Security Analytics', color: '#ca8a04' },
  { id: 20, name: 'Women Surrounded by Men', category: 'Crime Detection', color: '#ec4899' },
  { id: 21, name: 'Women/Infant Abduction', category: 'Crime Detection', color: '#991b1b' },
  { id: 22, name: 'Vehicle Monitoring', category: 'Vehicle Analytics', color: '#0284c7' },
  { id: 23, name: 'Zone Monitoring', category: 'Security Analytics', color: '#16a34a' }
];

const RULE_ALIASES = {
  'graffiti / vandalism': 'Graffiti and Vandalism Detection',
  'graffiti and vandalism': 'Graffiti and Vandalism Detection',
  'women surrounded': 'Women Surrounded by Men',
  'abduction detection': 'Women/Infant Abduction',
  'strike / procession': 'Strike / Morcha / Hartal / Procession',
  'zone monitoring (restricted area)': 'Zone Monitoring'
};

export const normalizeRuleName = (value = '') => {
  const compact = String(value).trim().toLowerCase().replace(/\s+/g, ' ');
  return RULE_ALIASES[compact] || String(value).trim();
};

export const getRuleMeta = (ruleOrName) => {
  if (typeof ruleOrName === 'number') {
    return DETECTION_RULES.find(rule => rule.id === ruleOrName) || null;
  }
  const normalized = normalizeRuleName(ruleOrName);
  return DETECTION_RULES.find(rule => rule.name.toLowerCase() === normalized.toLowerCase()) || null;
};

export const enrichRule = (rule) => {
  const meta = getRuleMeta(Number(rule?.id)) || getRuleMeta(rule?.name);
  return {
    ...meta,
    ...rule,
    name: meta?.name || normalizeRuleName(rule?.name || ''),
    category: rule?.category || meta?.category || 'Other',
    color: meta?.color || '#64748b'
  };
};

export const ruleNameMatches = (selected, eventName) => {
  if (!selected || selected === 'All Rules' || selected === 'all') return true;
  if (!eventName) return false;
  const left = normalizeRuleName(selected).toLowerCase();
  const right = normalizeRuleName(eventName).toLowerCase();
  return left === right || left.includes(right) || right.includes(left);
};

export const categoryMatches = (selected, eventCategory) => {
  if (!selected || selected === 'All Categories' || selected === 'all') return true;
  if (!eventCategory) return false;
  const left = String(selected).trim().toLowerCase();
  const right = String(eventCategory).trim().toLowerCase();
  return left === right || left.includes(right) || right.includes(left);
};

const cameraKeyCandidates = (camera) => {
  if (!camera) return [];
  const streamId = getCameraStreamId(camera);
  const keys = [camera.id, streamId, camera.name];
  if (camera.collectionName && camera.ip) keys.push(`${camera.collectionName}_${camera.ip}`);
  if (camera.collection && camera.ip) keys.push(`${camera.collection}_${camera.ip}`);
  return [...new Set(keys.filter(Boolean).map(String))];
};

const normalizedCameraKey = (value = '') => String(value)
  .toLowerCase()
  .replace(/^camera[-_]/, '')
  .replace(/[^a-z0-9]/g, '');

export const getRulesForCamera = (cameraRules = {}, camera) => {
  const candidates = cameraKeyCandidates(camera);
  for (const key of candidates) {
    if (Array.isArray(cameraRules[key])) return cameraRules[key].map(Number);
  }
  const normalizedCandidates = new Set(candidates.map(normalizedCameraKey));
  for (const [key, ruleIds] of Object.entries(cameraRules || {})) {
    if (normalizedCandidates.has(normalizedCameraKey(key)) && Array.isArray(ruleIds)) {
      return ruleIds.map(Number);
    }
  }
  return [];
};

export const eventMatchesCamera = (event, camera) => {
  if (!camera) return true;
  const eventKeys = [event?.camera_id, event?.camera_name, event?.source_id]
    .filter(Boolean)
    .map(normalizedCameraKey);
  const candidateKeys = cameraKeyCandidates(camera).map(normalizedCameraKey);
  return candidateKeys.some(candidate => eventKeys.some(eventKey => eventKey === candidate || eventKey.includes(candidate) || candidate.includes(eventKey)));
};

export const getConfiguredRuleIds = (cameraRules = {}, cameras = []) => {
  const ids = new Set();
  if (cameras.length) {
    cameras.forEach(camera => getRulesForCamera(cameraRules, camera).forEach(id => ids.add(Number(id))));
  } else {
    Object.values(cameraRules || {}).forEach(ruleIds => {
      if (Array.isArray(ruleIds)) ruleIds.forEach(id => ids.add(Number(id)));
    });
  }
  return ids;
};
