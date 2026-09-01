"""
Stream monitoring and health check utilities
"""

import time
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StreamHealthMonitor:
    """Monitor stream health and provide diagnostics"""
    
    def __init__(self):
        self.stream_stats: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
    def register_stream(self, stream_id: str, rtsp_url: str):
        """Register a new stream for monitoring"""
        with self.lock:
            self.stream_stats[stream_id] = {
                'rtsp_url': rtsp_url,
                'start_time': datetime.now(),
                'last_frame_time': None,
                'total_frames': 0,
                'connection_attempts': 0,
                'successful_connections': 0,
                'timeout_errors': 0,
                'general_errors': 0,
                'last_error': None,
                'last_error_time': None,
                'current_status': 'starting',
                'uptime_seconds': 0,
                'avg_fps': 0.0,
                'connection_stability': 'unknown'
            }
    
    def update_frame_received(self, stream_id: str):
        """Update stats when a frame is received"""
        with self.lock:
            if stream_id in self.stream_stats:
                stats = self.stream_stats[stream_id]
                now = datetime.now()
                stats['last_frame_time'] = now
                stats['total_frames'] += 1
                stats['current_status'] = 'active'
                
                # Calculate uptime and FPS
                uptime = (now - stats['start_time']).total_seconds()
                stats['uptime_seconds'] = uptime
                if uptime > 0:
                    stats['avg_fps'] = stats['total_frames'] / uptime
                
                # Determine connection stability
                if stats['total_frames'] > 100:  # Need some frames to assess
                    error_rate = (stats['timeout_errors'] + stats['general_errors']) / stats['connection_attempts'] if stats['connection_attempts'] > 0 else 0
                    if error_rate < 0.1:
                        stats['connection_stability'] = 'excellent'
                    elif error_rate < 0.3:
                        stats['connection_stability'] = 'good'
                    elif error_rate < 0.5:
                        stats['connection_stability'] = 'fair'
                    else:
                        stats['connection_stability'] = 'poor'
    
    def update_connection_attempt(self, stream_id: str, success: bool = False):
        """Update stats when a connection attempt is made"""
        with self.lock:
            if stream_id in self.stream_stats:
                stats = self.stream_stats[stream_id]
                stats['connection_attempts'] += 1
                if success:
                    stats['successful_connections'] += 1
                    stats['current_status'] = 'connected'
    
    def update_error(self, stream_id: str, error_msg: str, error_type: str = 'general'):
        """Update stats when an error occurs"""
        with self.lock:
            if stream_id in self.stream_stats:
                stats = self.stream_stats[stream_id]
                stats['last_error'] = error_msg
                stats['last_error_time'] = datetime.now()
                stats['current_status'] = 'error'
                
                if error_type == 'timeout':
                    stats['timeout_errors'] += 1
                else:
                    stats['general_errors'] += 1
    
    def get_stream_health(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get health information for a specific stream"""
        with self.lock:
            if stream_id in self.stream_stats:
                stats = self.stream_stats[stream_id].copy()
                
                # Add computed health metrics
                now = datetime.now()
                if stats['last_frame_time']:
                    seconds_since_last_frame = (now - stats['last_frame_time']).total_seconds()
                    stats['seconds_since_last_frame'] = seconds_since_last_frame
                    stats['is_receiving_frames'] = seconds_since_last_frame < 30
                else:
                    stats['seconds_since_last_frame'] = None
                    stats['is_receiving_frames'] = False
                
                # Convert datetime objects to strings for JSON serialization
                if stats['start_time']:
                    stats['start_time'] = stats['start_time'].isoformat()
                if stats['last_frame_time']:
                    stats['last_frame_time'] = stats['last_frame_time'].isoformat()
                if stats['last_error_time']:
                    stats['last_error_time'] = stats['last_error_time'].isoformat()
                
                return stats
            return None
    
    def get_all_streams_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health information for all streams"""
        with self.lock:
            result = {}
            for stream_id in self.stream_stats:
                result[stream_id] = self.get_stream_health(stream_id)
            return result
    
    def remove_stream(self, stream_id: str):
        """Remove a stream from monitoring"""
        with self.lock:
            if stream_id in self.stream_stats:
                del self.stream_stats[stream_id]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all streams"""
        with self.lock:
            total_streams = len(self.stream_stats)
            active_streams = 0
            error_streams = 0
            total_frames = 0
            total_errors = 0
            
            for stats in self.stream_stats.values():
                if stats['current_status'] == 'active':
                    active_streams += 1
                elif stats['current_status'] == 'error':
                    error_streams += 1
                
                total_frames += stats['total_frames']
                total_errors += stats['timeout_errors'] + stats['general_errors']
            
            return {
                'total_streams': total_streams,
                'active_streams': active_streams,
                'error_streams': error_streams,
                'idle_streams': total_streams - active_streams - error_streams,
                'total_frames_processed': total_frames,
                'total_errors': total_errors,
                'overall_error_rate': total_errors / max(total_frames, 1)
            }

# Global monitor instance
stream_monitor = StreamHealthMonitor()

def get_stream_diagnostics(stream_id: str) -> Dict[str, Any]:
    """Get comprehensive diagnostics for a stream"""
    health = stream_monitor.get_stream_health(stream_id)
    if not health:
        return {"error": "Stream not found"}
    
    # Add recommendations based on health data
    recommendations = []
    
    if health['connection_stability'] == 'poor':
        recommendations.append("Consider checking network connectivity to camera")
        recommendations.append("Verify camera credentials and RTSP URL")
    
    if health['timeout_errors'] > 5:
        recommendations.append("High timeout errors detected - camera may be overloaded")
        recommendations.append("Consider reducing frame rate or increasing timeout values")
    
    if not health['is_receiving_frames']:
        recommendations.append("No recent frames received - stream may be disconnected")
        recommendations.append("Check camera power and network connection")
    
    if health['avg_fps'] < 10:
        recommendations.append("Low frame rate detected - check network bandwidth")
    
    health['recommendations'] = recommendations
    return health
