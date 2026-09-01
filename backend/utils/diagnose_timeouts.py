#!/usr/bin/env python3
"""
RTSP Stream Timeout Diagnostic Tool

This script helps diagnose and fix RTSP stream timeout issues by:
1. Testing different timeout configurations
2. Analyzing connection methods
3. Providing recommendations for optimal settings
"""

import cv2
import time
import json
import os
import sys
from urllib.parse import urlparse

def mask_credentials(url):
    """Mask credentials in URL for safe logging"""
    try:
        parsed = urlparse(url)
        if parsed.username and parsed.password:
            masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                masked_netloc += f":{parsed.port}"
            return url.replace(parsed.netloc, masked_netloc)
    except:
        pass
    return url

def test_rtsp_connection(rtsp_url, timeout_open_ms, timeout_read_ms, buffer_size=3, test_frames=5):
    """Test RTSP connection with specific timeout settings"""
    print(f"  Testing: open={timeout_open_ms/1000}s, read={timeout_read_ms/1000}s, buffer={buffer_size}")
    
    cap = None
    try:
        start_time = time.time()
        cap = cv2.VideoCapture(rtsp_url)
        
        # Set timeout properties
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_open_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_read_ms)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size)
        cap.set(cv2.CAP_PROP_FPS, 25)
        
        if not cap.isOpened():
            return {
                'success': False,
                'error': 'Failed to open stream',
                'connection_time': time.time() - start_time
            }
        
        connection_time = time.time() - start_time
        
        # Test frame reading
        successful_frames = 0
        frame_times = []
        
        for i in range(test_frames):
            frame_start = time.time()
            ret, frame = cap.read()
            frame_time = time.time() - frame_start
            frame_times.append(frame_time)
            
            if ret and frame is not None:
                successful_frames += 1
            
            time.sleep(0.1)  # Small delay between reads
        
        avg_frame_time = sum(frame_times) / len(frame_times) if frame_times else 0
        
        return {
            'success': True,
            'connection_time': connection_time,
            'successful_frames': successful_frames,
            'total_frames': test_frames,
            'avg_frame_time': avg_frame_time,
            'max_frame_time': max(frame_times) if frame_times else 0,
            'frame_success_rate': successful_frames / test_frames * 100
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'connection_time': time.time() - start_time if 'start_time' in locals() else 0
        }
    finally:
        if cap:
            cap.release()

def diagnose_camera(camera_ip, rtsp_url):
    """Diagnose timeout issues for a specific camera"""
    print(f"\n🔍 Diagnosing camera {camera_ip}")
    print(f"   URL: {mask_credentials(rtsp_url)}")
    print("=" * 60)
    
    # Test different timeout configurations
    test_configs = [
        # (open_timeout_ms, read_timeout_ms, buffer_size, description)
        (30000, 60000, 3, "Current default settings"),
        (45000, 120000, 3, "Extended timeouts"),
        (60000, 180000, 5, "Maximum timeouts with larger buffer"),
        (25000, 90000, 2, "Moderate timeouts"),
        (15000, 30000, 1, "Minimal timeouts (fast networks only)"),
    ]
    
    results = []
    
    for open_timeout, read_timeout, buffer_size, description in test_configs:
        print(f"\n📊 {description}")
        result = test_rtsp_connection(rtsp_url, open_timeout, read_timeout, buffer_size)
        result['config'] = {
            'open_timeout_ms': open_timeout,
            'read_timeout_ms': read_timeout,
            'buffer_size': buffer_size,
            'description': description
        }
        results.append(result)
        
        if result['success']:
            print(f"  ✅ Success: {result['successful_frames']}/{result['total_frames']} frames")
            print(f"     Connection time: {result['connection_time']:.2f}s")
            print(f"     Avg frame time: {result['avg_frame_time']:.3f}s")
            print(f"     Max frame time: {result['max_frame_time']:.3f}s")
            print(f"     Success rate: {result['frame_success_rate']:.1f}%")
        else:
            print(f"  ❌ Failed: {result['error']}")
            print(f"     Time to failure: {result['connection_time']:.2f}s")
    
    return results

def analyze_results(camera_ip, results):
    """Analyze test results and provide recommendations"""
    print(f"\n📋 Analysis for camera {camera_ip}")
    print("=" * 60)
    
    successful_configs = [r for r in results if r['success'] and r['frame_success_rate'] >= 80]
    
    if not successful_configs:
        print("❌ No configurations worked reliably")
        print("   Recommendations:")
        print("   - Check network connectivity to camera")
        print("   - Verify RTSP URL and credentials")
        print("   - Check camera RTSP server settings")
        print("   - Try accessing camera directly with VLC")
        return None
    
    # Find best configuration
    best_config = max(successful_configs, key=lambda x: (x['frame_success_rate'], -x['avg_frame_time']))
    
    print(f"✅ Best configuration: {best_config['config']['description']}")
    print(f"   Open timeout: {best_config['config']['open_timeout_ms']/1000}s")
    print(f"   Read timeout: {best_config['config']['read_timeout_ms']/1000}s")
    print(f"   Buffer size: {best_config['config']['buffer_size']}")
    print(f"   Success rate: {best_config['frame_success_rate']:.1f}%")
    print(f"   Avg frame time: {best_config['avg_frame_time']:.3f}s")
    
    # Provide specific recommendations
    print("\n💡 Recommendations:")
    
    if best_config['config']['open_timeout_ms'] > 45000:
        print("   - Camera has slow connection establishment")
        print("   - Consider network optimization or camera settings")
    
    if best_config['avg_frame_time'] > 0.5:
        print("   - Slow frame delivery detected")
        print("   - Consider reducing camera resolution or frame rate")
    
    if best_config['config']['buffer_size'] > 3:
        print("   - Large buffer needed for stability")
        print("   - Network may have intermittent issues")
    
    return best_config

def main():
    """Main diagnostic function"""
    print("🔧 RTSP Stream Timeout Diagnostic Tool")
    print("=" * 60)
    
    # Load camera configuration
    config_path = "data/camera_configuration.json"
    if not os.path.exists(config_path):
        print(f"❌ Camera configuration not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        camera_data = json.load(f)
    
    all_results = {}
    
    for collection_name, cameras in camera_data.items():
        print(f"\n🏢 Collection: {collection_name}")
        
        for camera_ip, rtsp_url in cameras.items():
            results = diagnose_camera(camera_ip, rtsp_url)
            best_config = analyze_results(camera_ip, results)
            
            all_results[f"{collection_name}_{camera_ip}"] = {
                'camera_ip': camera_ip,
                'rtsp_url': mask_credentials(rtsp_url),
                'collection': collection_name,
                'test_results': results,
                'best_config': best_config
            }
    
    # Generate summary report
    print("\n📊 SUMMARY REPORT")
    print("=" * 60)
    
    working_cameras = sum(1 for r in all_results.values() if r['best_config'])
    total_cameras = len(all_results)
    
    print(f"Working cameras: {working_cameras}/{total_cameras}")
    
    if working_cameras > 0:
        print("\n🔧 Recommended timeout settings for main.py:")
        
        # Calculate optimal settings based on successful configurations
        successful_configs = [r['best_config'] for r in all_results.values() if r['best_config']]
        
        avg_open_timeout = sum(c['config']['open_timeout_ms'] for c in successful_configs) / len(successful_configs)
        avg_read_timeout = sum(c['config']['read_timeout_ms'] for c in successful_configs) / len(successful_configs)
        avg_buffer_size = sum(c['config']['buffer_size'] for c in successful_configs) / len(successful_configs)
        
        print(f"   'timeout_open': {int(avg_open_timeout)},  # {avg_open_timeout/1000:.1f} seconds")
        print(f"   'timeout_read': {int(avg_read_timeout)},  # {avg_read_timeout/1000:.1f} seconds")
        print(f"   'buffer_size': {int(avg_buffer_size)}")
    
    # Save detailed results
    with open('timeout_diagnostic_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: timeout_diagnostic_results.json")

if __name__ == "__main__":
    main()
