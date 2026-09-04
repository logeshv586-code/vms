import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useCameraStore } from '../../store/cameraStore';
import { getCameraStreamId } from '../../utils/cameraUtils';
import LegacyAIDetectionTab from './AIDetectionTabLegacy';

const classColor = (label) => {
  const value = String(label || '').toLowerCase();
  if (value === 'person') return '#00ffcc';
  if (['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'vehicle'].includes(value)) return '#0088ff';
  if (['weapon', 'gun', 'knife', 'fire', 'smoke'].includes(value)) return '#ff3366';
  if (['bag', 'backpack', 'suitcase', 'handbag'].includes(value)) return '#ffa500';
  return '#ffd166';
};

const CenterPointOverlay = ({ viewport }) => {
  const { selectedAiCamera } = useCameraStore();
  const [payload, setPayload] = useState({ detections: [], frame_width: 640, frame_height: 480 });
  const [geometry, setGeometry] = useState(null);

  useEffect(() => {
    if (!selectedAiCamera) {
      setPayload({ detections: [], frame_width: 640, frame_height: 480 });
      return undefined;
    }

    const streamId = getCameraStreamId(selectedAiCamera);
    let mounted = true;

    const refresh = async () => {
      try {
        const response = await fetch(`/api/stream/detections/${streamId}`);
        const data = await response.json();
        if (mounted && data) setPayload(data);
      } catch (_) {
        // The existing AI panel owns stream error presentation.
      }
    };

    refresh();
    const timer = window.setInterval(refresh, 250);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [selectedAiCamera]);

  useEffect(() => {
    if (!viewport) return undefined;

    const measure = () => {
      const image = viewport.querySelector('img.detection-image');
      const containerWidth = viewport.clientWidth || 0;
      const containerHeight = viewport.clientHeight || 0;
      const imageWidth = image?.naturalWidth || Number(payload.frame_width) || 640;
      const imageHeight = image?.naturalHeight || Number(payload.frame_height) || 480;
      if (!containerWidth || !containerHeight || !imageWidth || !imageHeight) return;

      const imageRatio = imageWidth / imageHeight;
      const containerRatio = containerWidth / containerHeight;
      let renderWidth;
      let renderHeight;
      let offsetX;
      let offsetY;

      if (containerRatio > imageRatio) {
        renderHeight = containerHeight;
        renderWidth = containerHeight * imageRatio;
        offsetX = (containerWidth - renderWidth) / 2;
        offsetY = 0;
      } else {
        renderWidth = containerWidth;
        renderHeight = containerWidth / imageRatio;
        offsetX = 0;
        offsetY = (containerHeight - renderHeight) / 2;
      }

      setGeometry({ containerWidth, containerHeight, renderWidth, renderHeight, offsetX, offsetY });
    };

    measure();
    const resizeObserver = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    resizeObserver?.observe(viewport);
    const image = viewport.querySelector('img.detection-image');
    image?.addEventListener('load', measure);
    window.addEventListener('resize', measure);

    return () => {
      resizeObserver?.disconnect();
      image?.removeEventListener('load', measure);
      window.removeEventListener('resize', measure);
    };
  }, [viewport, payload.frame_width, payload.frame_height]);

  const points = useMemo(() => {
    if (!geometry) return [];
    const frameWidth = Math.max(1, Number(payload.frame_width) || 640);
    const frameHeight = Math.max(1, Number(payload.frame_height) || 480);

    return (payload.detections || []).map((det, index) => {
      const normalized = det.norm_centroid || det.normalized_centroid;
      const center = det.centroid || det.center;
      let nx;
      let ny;

      if (Array.isArray(normalized) && normalized.length >= 2) {
        nx = Number(normalized[0]);
        ny = Number(normalized[1]);
      } else if (Array.isArray(center) && center.length >= 2) {
        nx = Number(center[0]) / frameWidth;
        ny = Number(center[1]) / frameHeight;
      } else {
        const box = det.bbox || det.box;
        if (!Array.isArray(box) || box.length !== 4) return null;
        nx = ((Number(box[0]) + Number(box[2])) / 2) / frameWidth;
        ny = ((Number(box[1]) + Number(box[3])) / 2) / frameHeight;
      }

      if (!Number.isFinite(nx) || !Number.isFinite(ny)) return null;
      nx = Math.max(0, Math.min(1, nx));
      ny = Math.max(0, Math.min(1, ny));
      return {
        key: `${det.track_id ?? det.id ?? 'object'}-${index}`,
        x: geometry.offsetX + nx * geometry.renderWidth,
        y: geometry.offsetY + ny * geometry.renderHeight,
        label: det.class_name || det.class || det.label || 'object',
        trackId: det.track_id ?? det.id,
      };
    }).filter(Boolean);
  }, [geometry, payload]);

  if (!viewport || !geometry || points.length === 0) return null;

  return createPortal(
    <svg
      aria-hidden="true"
      width={geometry.containerWidth}
      height={geometry.containerHeight}
      viewBox={`0 0 ${geometry.containerWidth} ${geometry.containerHeight}`}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
        zIndex: 7,
      }}
    >
      {points.map((point) => {
        const color = classColor(point.label);
        return (
          <g key={point.key}>
            <circle cx={point.x} cy={point.y} r="9" fill="none" stroke="#ffffff" strokeWidth="1.25" opacity="0.9" />
            <circle cx={point.x} cy={point.y} r="5" fill={color} stroke="#000000" strokeWidth="1" />
            <line x1={point.x - 13} y1={point.y} x2={point.x - 7} y2={point.y} stroke={color} strokeWidth="1.5" />
            <line x1={point.x + 7} y1={point.y} x2={point.x + 13} y2={point.y} stroke={color} strokeWidth="1.5" />
            <line x1={point.x} y1={point.y - 13} x2={point.x} y2={point.y - 7} stroke={color} strokeWidth="1.5" />
            <line x1={point.x} y1={point.y + 7} x2={point.x} y2={point.y + 13} stroke={color} strokeWidth="1.5" />
          </g>
        );
      })}
    </svg>,
    viewport
  );
};

const AIDetectionTab = () => {
  const rootRef = useRef(null);
  const [viewport, setViewport] = useState(null);

  useEffect(() => {
    const resolveViewport = () => {
      const nextViewport = rootRef.current?.querySelector('.video-viewport') || null;
      setViewport((current) => (current === nextViewport ? current : nextViewport));
    };

    resolveViewport();
    const observer = new MutationObserver(resolveViewport);
    if (rootRef.current) observer.observe(rootRef.current, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={rootRef} style={{ display: 'contents' }}>
      <LegacyAIDetectionTab />
      <CenterPointOverlay viewport={viewport} />
    </div>
  );
};

export default AIDetectionTab;
