import os
import json
import subprocess
import threading
import time
import logging
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
# Set up logging
logger = logging.getLogger(__name__)

class ArchiveRecordingManager:
    """Manages FFmpeg-based recording processes for RTSP streams"""
    
    def __init__(self, camera_config_path: str, recordings_base_path: str = "./recordings"):
        self.camera_config_path = camera_config_path
        self.recordings_base_path = Path(recordings_base_path)
        self.recording_processes: Dict[str, subprocess.Popen] = {}
        self.recording_threads: Dict[str, threading.Thread] = {}
        self.should_stop = threading.Event()
        self.cleanup_thread = None
        
        # Configure FFmpeg path (check for local installation first)
        self.ffmpeg_path = "ffmpeg"
        
        # Possible local paths
        possible_paths = [
            Path(__file__).parent.parent / "ffmpeg-master-latest-win64-gpl-shared" / "bin" / "ffmpeg.exe",
            Path(__file__).parent.parent / "ffmpeg" / "ffmpeg.exe"
        ]
        
        for path in possible_paths:
            if path.exists():
                self.ffmpeg_path = str(path)
                logger.info(f"Using local FFmpeg: {self.ffmpeg_path}")
                break
        else:
            logger.warning("Local FFmpeg not found, falling back to system 'ffmpeg'")
        
        # Ensure recordings directory exists
        self.recordings_base_path.mkdir(exist_ok=True)
        
        # Start cleanup thread
        self._start_cleanup_thread()

        # Scan and validate existing recordings
        self._scan_existing_recordings()
    
    def _start_cleanup_thread(self):
        """Start the cleanup thread for old recordings"""
        self.cleanup_thread = threading.Thread(target=self._cleanup_old_recordings, daemon=True)
        self.cleanup_thread.start()
        logger.info("Started cleanup thread for old recordings")

    def _scan_existing_recordings(self):
        """Scan existing recordings and validate file integrity"""
        try:
            if not self.recordings_base_path.exists():
                logger.info("Recordings directory does not exist yet")
                return

            total_recordings = 0
            valid_recordings = 0
            corrupted_files = []

            logger.info("Starting comprehensive scan of existing recordings...")

            for stream_dir in self.recordings_base_path.iterdir():
                if stream_dir.is_dir() and stream_dir.name != 'quarantine' and not stream_dir.name.startswith('.'):
                    stream_id = stream_dir.name
                    logger.debug(f"Scanning recordings for stream: {stream_id}")

                    for recording_file in stream_dir.glob("*.mp4"):
                        total_recordings += 1

                        # Enhanced file validation
                        try:
                            file_size = recording_file.stat().st_size

                            # Check if file is empty or very small (likely corrupted)
                            if file_size < 51200:  # Less than 50KB is likely corrupted/too short
                                corrupted_files.append(recording_file)
                                logger.warning(f"Found corrupted recording (too small): {recording_file} (size: {file_size} bytes)")
                                continue

                            # Check if file is currently being written to
                            if self._is_file_being_written(recording_file):
                                logger.debug(f"File currently being written: {recording_file.name}")
                                valid_recordings += 1  # Count as valid but being written
                                continue

                            # Validate MP4 structure
                            if self._validate_mp4_structure(recording_file):
                                valid_recordings += 1
                                logger.debug(f"Valid recording: {recording_file.name} ({file_size} bytes)")
                            else:
                                corrupted_files.append(recording_file)
                                logger.warning(f"Found corrupted recording (invalid MP4): {recording_file}")

                        except OSError as e:
                            logger.error(f"Error checking file {recording_file}: {e}")
                            corrupted_files.append(recording_file)

            logger.info(f"Scan complete: {valid_recordings}/{total_recordings} valid recordings found")

            # Handle corrupted files by moving to quarantine
            if corrupted_files:
                logger.warning(f"Found {len(corrupted_files)} corrupted files")
                self._quarantine_corrupted_files(corrupted_files)

        except Exception as e:
            logger.error(f"Error scanning existing recordings: {e}")

    def _is_file_being_written(self, file_path: Path) -> bool:
        """Check if a file is currently being written to"""
        try:
            # Try to open file in exclusive mode (Windows) or check lock (Unix)
            if os.name == 'nt':  # Windows
                try:
                    # Try to open with exclusive access
                    with open(file_path, 'r+b') as f:
                        return False  # If we can open it exclusively, it's not being written
                except (PermissionError, OSError):
                    return True  # File is likely being written to
            else:  # Unix-like systems
                try:
                    import fcntl
                    with open(file_path, 'r+b') as f:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        return False
                except (IOError, OSError):
                    return True
        except Exception as e:
            logger.debug(f"Error checking if file is being written {file_path}: {e}")
            return False  # Assume not being written if we can't determine

    def _validate_mp4_structure(self, file_path: Path) -> bool:
        """Validate MP4 file structure using basic checks"""
        try:
            # Check file size
            if file_path.stat().st_size < 51200:  # Less than 50KB
                return False

            # Check MP4 signature and structure
            with open(file_path, 'rb') as f:
                header = f.read(32)
                if len(header) < 8:
                    return False

                # Check for ftyp box (MP4 signature)
                if b'ftyp' not in header[:20]:
                    return False

                # Check for common MP4 brands
                brands = [b'isom', b'mp41', b'mp42', b'avc1', b'mp4v']
                if not any(brand in header for brand in brands):
                    return False

            return True
        except Exception as e:
            logger.error(f"Error validating MP4 structure for {file_path}: {e}")
            return False

    def _quarantine_corrupted_files(self, corrupted_files: List[Path]):
        """Move corrupted files to quarantine directory instead of deleting"""
        if not corrupted_files:
            return

        try:
            quarantine_dir = self.recordings_base_path / "quarantine"
            quarantine_dir.mkdir(exist_ok=True)

            for corrupted_file in corrupted_files:
                try:
                    # Check if file is already in quarantine
                    if corrupted_file.parent == quarantine_dir:
                        logger.debug(f"File already in quarantine: {corrupted_file}")
                        continue

                    # Create unique quarantine filename
                    timestamp = int(time.time())
                    # Clean the filename if it already has corrupted suffixes to prevent long names
                    clean_stem = corrupted_file.stem
                    if "_corrupted_" in clean_stem:
                        clean_stem = clean_stem.split("_corrupted_")[0]
                    
                    quarantine_name = f"{clean_stem}_corrupted_{timestamp}.mp4"
                    quarantine_path = quarantine_dir / quarantine_name

                    # Move file to quarantine
                    corrupted_file.rename(quarantine_path)
                    logger.info(f"Moved corrupted file to quarantine: {quarantine_path}")

                except Exception as e:
                    logger.error(f"Failed to quarantine corrupted file {corrupted_file}: {e}")
                    # If quarantine fails, try to delete the file
                    try:
                        corrupted_file.unlink()
                        logger.info(f"Deleted corrupted file: {corrupted_file}")
                    except Exception as delete_error:
                        logger.error(f"Failed to delete corrupted file {corrupted_file}: {delete_error}")

        except Exception as e:
            logger.error(f"Error setting up quarantine directory: {e}")

    def _parse_timestamp_from_filename(self, filename: str) -> Optional[datetime]:
        """Extract YYYY-MM-DD_HH-MM-SS timestamp from potentially complex filenames"""
        try:
            # Suffixes like _corrupted or _v2 can be present
            # Format: 2026-04-06_17-41-40 (19 chars)
            base_part = filename[:19]
            return datetime.strptime(base_part, "%Y-%m-%d_%H-%M-%S")
        except (ValueError, IndexError):
            return None

    def _cleanup_old_recordings(self):
        """Remove recordings older than 30 days (runs hourly)"""
        while not self.should_stop.wait(3600):  # Wait 1 hour
            try:
                cutoff_date = datetime.now() - timedelta(days=30)
                logger.info(f"Starting cleanup of recordings older than {cutoff_date}")
                
                for stream_dir in self.recordings_base_path.iterdir():
                    if stream_dir.is_dir() and not stream_dir.name.startswith('.'):
                        # Find all .mp4 files in the stream directory
                        for recording_file in stream_dir.glob("*.mp4"):
                            try:
                                # Parse filename robustly
                                file_date = self._parse_timestamp_from_filename(recording_file.stem)
                                
                                if file_date and file_date < cutoff_date:
                                    recording_file.unlink()
                                    logger.info(f"Deleted old recording: {recording_file}")
                            except (ValueError, OSError) as e:
                                logger.warning(f"Error processing file {recording_file}: {e}")
                
                logger.info("Cleanup cycle completed")
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")
    
    def _load_camera_config(self) -> Dict:
        """Load camera configuration from JSON file"""
        try:
            with open(self.camera_config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading camera configuration: {e}")
            return {}
    
    def _get_stream_id(self, collection_name: str, camera_ip: str) -> str:
        """Generate consistent stream ID"""
        return f"{collection_name}_{camera_ip}"
    
    def _create_recording_directory(self, stream_id: str) -> Path:
        """Create and return recording directory for stream"""
        stream_dir = self.recordings_base_path / stream_id
        stream_dir.mkdir(exist_ok=True)
        return stream_dir
    
    def _get_current_filename(self, stream_id: str) -> str:
        """Generate unique filename for current recording segment"""
        now = datetime.now()
        base_filename = now.strftime("%Y-%m-%d_%H-%M-%S")

        # Check if file already exists and generate unique name
        stream_dir = self._create_recording_directory(stream_id)
        counter = 0

        while True:
            if counter == 0:
                filename = f"{base_filename}.mp4"
            else:
                filename = f"{base_filename}_{counter:03d}.mp4"

            output_path = stream_dir / filename
            if not output_path.exists():
                return filename

            counter += 1
            # Prevent infinite loop - if we have 1000 files with same timestamp, use microseconds
            if counter >= 1000:
                microsecond_suffix = now.strftime("%f")[:3]  # First 3 digits of microseconds
                filename = f"{base_filename}_{microsecond_suffix}.mp4"
                break

        return filename
    
    def _finalize_recording(self, recording_path: Path):
        """Finalize a fragmented MP4 by remuxing to standard MP4 with moov at start.
        Runs in a background thread so the next recording starts immediately."""
        try:
            if not recording_path.exists():
                return
            
            file_size = recording_path.stat().st_size
            if file_size < 51200:  # Skip very small files
                logger.debug(f"Skipping finalization of small file: {recording_path.name} ({file_size} bytes)")
                return

            temp_path = recording_path.with_name(recording_path.stem + ".finalizing.mp4")
            
            logger.info(f"Finalizing recording: {recording_path.name} ({file_size / (1024*1024):.1f} MB)")
            
            # Fast remux: copy streams and move moov atom to start
            finalize_cmd = [
                self.ffmpeg_path,
                '-y',
                '-i', str(recording_path),
                '-c', 'copy',
                '-movflags', '+faststart',
                '-avoid_negative_ts', 'make_zero',
                str(temp_path)
            ]
            
            result = subprocess.run(
                finalize_cmd,
                capture_output=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0 and temp_path.exists() and temp_path.stat().st_size >= 10240:
                # Replace original with finalized version
                try:
                    recording_path.unlink()
                    temp_path.rename(recording_path)
                    logger.info(f"Successfully finalized: {recording_path.name}")
                except Exception as rename_err:
                    logger.error(f"Error replacing original with finalized file: {rename_err}")
                    # Clean up temp file if rename failed
                    if temp_path.exists():
                        try:
                            temp_path.unlink()
                        except Exception:
                            pass
            else:
                stderr_msg = result.stderr.decode(errors='ignore')[:200] if result.stderr else 'unknown'
                logger.warning(f"Finalization failed for {recording_path.name}: {stderr_msg}")
                # Clean up failed temp file
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
                        
            # Also clean up any old .converted.mp4 files since the original is now finalized
            converted_path = recording_path.with_name(recording_path.stem + ".converted.mp4")
            if converted_path.exists():
                try:
                    converted_path.unlink()
                    logger.debug(f"Cleaned up old converted file: {converted_path.name}")
                except Exception:
                    pass
                    
        except subprocess.TimeoutExpired:
            logger.error(f"Finalization timed out for {recording_path.name}")
            temp_path = recording_path.with_name(recording_path.stem + ".finalizing.mp4")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error finalizing recording {recording_path}: {e}")

    def _start_recording_process(self, stream_id: str, rtsp_url: str):
        """Start FFmpeg recording process for a single stream using fragmented MP4.
        
        Uses fragmented MP4 format (frag_keyframe+empty_moov) which embeds metadata 
        throughout the file, making recordings playable even if FFmpeg is killed 
        mid-recording. Each segment is limited to 1 hour via -t flag. After each 
        segment completes, a background thread finalizes it by remuxing to standard 
        MP4 with moov atom at the start for optimal browser seeking.
        """
        try:
            stream_dir = self._create_recording_directory(stream_id)

            while not self.should_stop.is_set():
                # Generate unique filename for this segment
                output_filename = self._get_current_filename(stream_id)
                output_path = stream_dir / output_filename
                
                logger.info(f"Starting 1-hour recording segment for {stream_id}: {output_filename}")

                ffmpeg_cmd = [
                    self.ffmpeg_path,
                    '-rtsp_transport', 'tcp',  # Use TCP for more reliable transport
                    '-i', rtsp_url,
                    # Video transcoding settings for universal compatibility
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',  # Fast encoding to conserve CPU
                    '-crf', '23',
                    '-profile:v', 'main',
                    '-level:v', '4.0',
                    '-pix_fmt', 'yuv420p',  # Force standard pixel format (avoid yuvj420p)
                    '-color_range', 'tv',   # Force TV color range
                    # Audio transcoding settings
                    '-c:a', 'aac',
                    '-strict', 'experimental',
                    '-b:a', '128k',
                    '-ar', '44100',
                    # Fragmented MP4 - playable even if FFmpeg is killed mid-recording
                    # frag_keyframe: start a new fragment at each keyframe
                    # empty_moov: write an empty moov at start (no final moov needed)
                    # default_base_moof: use moof as base for data offsets (better compatibility)
                    '-movflags', '+frag_keyframe+empty_moov+default_base_moof',
                    '-frag_duration', '2000000',   # 2-second fragments for fine granularity
                    '-min_frag_duration', '1000000', # Minimum 1-second fragments
                    # Container and streaming settings
                    '-avoid_negative_ts', 'make_zero',
                    '-fflags', '+genpts+flush_packets',
                    '-max_muxing_queue_size', '1024',
                    '-use_wallclock_as_timestamps', '1',
                    '-thread_queue_size', '512',
                    # Error handling
                    '-err_detect', 'ignore_err',
                    '-max_error_rate', '0.1',
                    # Record for 1 hour max, then rotate to new file
                    '-t', '3600',
                    str(output_path)
                ]
                
                logger.info(f"Starting FFmpeg for {stream_id} (PID pending): {output_filename}")
                
                try:
                    process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )

                    self.recording_processes[stream_id] = process
                    logger.info(f"Started FFmpeg process for {stream_id} (PID: {process.pid}), output: {output_filename}")

                    # Wait for process to complete (either 1-hour timeout or error)
                    process.wait()

                    # After segment completes, finalize it in the background
                    if output_path.exists() and output_path.stat().st_size > 0:
                        finalize_thread = threading.Thread(
                            target=self._finalize_recording,
                            args=(output_path,),
                            daemon=True,
                            name=f"Finalize-{output_filename}"
                        )
                        finalize_thread.start()
                        logger.info(f"Started background finalization for {output_filename}")

                    # Handle process completion/exit
                    if process.returncode != 0 and not self.should_stop.is_set():
                        logger.error(f"FFmpeg process for {stream_id} exited with error code {process.returncode}")
                        # Wait before restarting to avoid rapid loops on persistent failure
                        time.sleep(30)
                    else:
                        logger.info(f"FFmpeg process for {stream_id} completed segment {output_filename}")
                        # Small delay before starting next segment
                        time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error in FFmpeg process for {stream_id}: {e}")
                    time.sleep(30)
                finally:
                    # Clean up process reference
                    if stream_id in self.recording_processes:
                        del self.recording_processes[stream_id]
                
        except Exception as e:
            logger.error(f"Error in recording thread for {stream_id}: {e}")



    def start_all_recordings(self):
        """Start recording processes for all configured cameras"""
        camera_config = self._load_camera_config()

        if not camera_config:
            logger.warning("No camera configuration found, no recordings will be started")
            return

        logger.info("Starting recording processes for all configured cameras")

        # Reset stop event to ensure threads can start
        self.should_stop.clear()

        for collection_name, cameras in camera_config.items():
            for camera_ip, rtsp_url in cameras.items():
                stream_id = self._get_stream_id(collection_name, camera_ip)

                # Skip if already recording
                if stream_id in self.recording_threads and self.recording_threads[stream_id].is_alive():
                    logger.info(f"Recording already active for {stream_id}")
                    continue

                # Clean up dead thread references
                if stream_id in self.recording_threads and not self.recording_threads[stream_id].is_alive():
                    del self.recording_threads[stream_id]

                # Start recording thread
                thread = threading.Thread(
                    target=self._start_recording_process,
                    args=(stream_id, rtsp_url),
                    daemon=True,
                    name=f"Recording-{stream_id}"
                )
                thread.start()
                self.recording_threads[stream_id] = thread

                logger.info(f"Started recording thread for {stream_id}")

                # Small delay to prevent overwhelming the system
                time.sleep(1)

        logger.info(f"Started {len(self.recording_threads)} recording processes")

        # Verify recordings started successfully
        self._verify_recording_startup()

    def _verify_recording_startup(self):
        """Verify that recording processes started successfully"""
        time.sleep(5)  # Wait for processes to initialize

        failed_streams = []
        for stream_id, thread in self.recording_threads.items():
            if not thread.is_alive():
                failed_streams.append(stream_id)
                logger.error(f"Recording thread for {stream_id} failed to start or died immediately")

        if failed_streams:
            logger.warning(f"Failed to start recordings for {len(failed_streams)} streams: {failed_streams}")
        else:
            logger.info("All recording processes verified as running successfully")

    def restart_failed_recordings(self):
        """Restart any failed recording processes"""
        camera_config = self._load_camera_config()
        if not camera_config:
            return

        restarted_count = 0
        for collection_name, cameras in camera_config.items():
            for camera_ip, rtsp_url in cameras.items():
                stream_id = self._get_stream_id(collection_name, camera_ip)

                # Check if thread exists and is alive
                if stream_id not in self.recording_threads or not self.recording_threads[stream_id].is_alive():
                    logger.info(f"Restarting failed recording for {stream_id}")

                    # Clean up dead thread reference
                    if stream_id in self.recording_threads:
                        del self.recording_threads[stream_id]

                    # Start new recording thread
                    thread = threading.Thread(
                        target=self._start_recording_process,
                        args=(stream_id, rtsp_url),
                        daemon=True,
                        name=f"Recording-{stream_id}"
                    )
                    thread.start()
                    self.recording_threads[stream_id] = thread
                    restarted_count += 1

        if restarted_count > 0:
            logger.info(f"Restarted {restarted_count} failed recording processes")

    def stop_recording(self, stream_id: str):
        """Stop recording for a specific stream"""
        try:
            # Stop the process
            if stream_id in self.recording_processes:
                process = self.recording_processes[stream_id]
                if os.name == 'nt':  # Windows
                    process.terminate()
                else:  # Unix-like systems
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)

                # Wait for process to terminate
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't terminate gracefully
                    if os.name == 'nt':
                        process.kill()
                    else:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)

                del self.recording_processes[stream_id]
                logger.info(f"Stopped recording process for {stream_id}")

            # Clean up thread reference
            if stream_id in self.recording_threads:
                del self.recording_threads[stream_id]

        except Exception as e:
            logger.error(f"Error stopping recording for {stream_id}: {e}")

    def stop_all_recordings(self):
        """Stop all recording processes"""
        logger.info("Stopping all recording processes")

        # Signal all threads to stop
        self.should_stop.set()

        # Stop all recording processes
        for stream_id in list(self.recording_processes.keys()):
            self.stop_recording(stream_id)

        # Wait for threads to finish
        for thread in self.recording_threads.values():
            if thread.is_alive():
                thread.join(timeout=5)

        self.recording_threads.clear()
        logger.info("All recording processes stopped")

    def get_recording_status(self) -> Dict:
        """Get current recording status for all streams"""
        # Count active recordings based on alive threads, not just active processes
        # This is because threads may be waiting for files to rotate but are still "recording"
        active_stream_ids = []
        for stream_id, thread in self.recording_threads.items():
            if thread.is_alive():
                active_stream_ids.append(stream_id)

        status = {
            "active_recordings": len(active_stream_ids),
            "stream_ids": active_stream_ids,
            "thread_status": {},
            "process_status": {}
        }

        # Check thread status
        for stream_id, thread in self.recording_threads.items():
            status["thread_status"][stream_id] = {
                "alive": thread.is_alive(),
                "name": thread.name
            }

        # Check process status
        for stream_id, process in self.recording_processes.items():
            try:
                # Check if process is still running
                poll_result = process.poll()
                status["process_status"][stream_id] = {
                    "running": poll_result is None,
                    "return_code": poll_result,
                    "pid": process.pid
                }
            except Exception as e:
                logger.error(f"Error checking process {stream_id}: {e}")
                status["process_status"][stream_id] = {
                    "running": False,
                    "error": str(e)
                }

        return status

    def get_current_recordings(self):
        """Get list of currently recording files that can be viewed while recording"""
        current_recordings = []

        try:
            # Iterate through all stream directories
            for stream_dir in self.recordings_base_path.iterdir():
                if not stream_dir.is_dir():
                    continue

                stream_id = stream_dir.name

                # Check if this stream is currently recording by checking thread status
                # This is more reliable than checking process status since threads persist
                # across process restarts during file rotation or error recovery
                if stream_id not in self.recording_threads or not self.recording_threads[stream_id].is_alive():
                    continue

                # Find the most recent MP4 file that's currently being written to
                mp4_files = list(stream_dir.glob("*.mp4"))
                if not mp4_files:
                    continue

                # Sort by modification time to get the most recent
                mp4_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                current_file = mp4_files[0]

                # Check if file is recent (within last 10 minutes) and has content
                # Allow size 0 if the stream is actively recording
                file_stat = current_file.stat()

                # Determine recording status more accurately
                is_actively_recording = False
                process_status = "unknown"

                # Check if there's an active process for this stream
                if stream_id in self.recording_processes:
                    process = self.recording_processes[stream_id]
                    if process and process.poll() is None:
                        is_actively_recording = True
                        process_status = "recording"
                    else:
                        process_status = "restarting"
                else:
                    # Thread is alive but no process - likely restarting
                    process_status = "restarting"
                    # Still consider it recording if file is very recent (last 2 minutes)
                    if (time.time() - file_stat.st_mtime) < 120:
                        is_actively_recording = True

                if (time.time() - file_stat.st_mtime) < 600 and (file_stat.st_size >= 10240 or is_actively_recording):
                    # Parse stream info
                    collection_name, camera_ip = stream_id.split('_', 1)

                    current_recordings.append({
                        "stream_id": stream_id,
                        "collection_name": collection_name,
                        "camera_ip": camera_ip,
                        "filename": current_file.name,
                        "file_path": str(current_file),
                        "file_size": file_stat.st_size,
                        "start_time": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
                        "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                        "duration_seconds": int(time.time() - file_stat.st_ctime),
                        "is_recording": is_actively_recording,
                        "process_status": process_status,
                        "can_view": True
                    })

        except Exception as e:
            logger.error(f"Error getting current recordings: {e}")

        return current_recordings

    def get_available_recordings(self, stream_id: str) -> List[str]:
        """Get list of available recording files for a stream"""
        try:
            stream_dir = self.recordings_base_path / stream_id
            if not stream_dir.exists():
                return []

            # Find all .mp4 files and sort by filename (which includes timestamp)
            recordings = []
            for recording_file in stream_dir.glob("*.mp4"):
                if not recording_file.name.endswith('.converted.mp4') and not recording_file.name.endswith('.finalizing.mp4'):
                    recordings.append(recording_file.name)

            # Sort by filename (timestamp) in descending order (newest first)
            recordings.sort(reverse=True)
            return recordings

        except Exception as e:
            logger.error(f"Error getting recordings for {stream_id}: {e}")
            return []

    def get_all_recordings(self, force_refresh: bool = False) -> List[Dict]:
        """Get all recordings across all streams with metadata"""
        try:
            all_recordings = []

            if not self.recordings_base_path.exists():
                logger.debug("Recordings directory does not exist")
                return all_recordings

            # Force refresh file system cache if requested
            if force_refresh:
                logger.debug("Force refreshing file system cache")
                self._refresh_filesystem_cache()

            logger.debug(f"Scanning recordings directory: {self.recordings_base_path}")

            for stream_dir in self.recordings_base_path.iterdir():
                if stream_dir.is_dir() and not stream_dir.name.startswith('.') and stream_dir.name != 'quarantine':
                    stream_id = stream_dir.name
                    logger.debug(f"Processing stream directory: {stream_id}")

                    # Get all recordings for this stream
                    recording_files = list(stream_dir.glob("*.mp4"))
                    # Filter out internal working files (converted, finalizing)
                    recording_files = [f for f in recording_files 
                                      if not f.name.endswith('.converted.mp4') 
                                      and not f.name.endswith('.finalizing.mp4')]
                    logger.debug(f"Found {len(recording_files)} MP4 files in {stream_id}")

                    for recording_file in recording_files:
                        try:
                            # Skip files that are currently being written
                            if self._is_file_being_written(recording_file):
                                logger.debug(f"Skipping file being written: {recording_file.name}")
                                continue

                            # Validate file before including
                            file_size = recording_file.stat().st_size
                            if file_size < 51200:  # Skip very small files (< 50KB)
                                logger.debug(f"Skipping small/unplayable file: {recording_file.name} ({file_size} bytes)")
                                # If older than 1 minute, quarantine it dynamically
                                try:
                                    mtime = recording_file.stat().st_mtime
                                    if (time.time() - mtime) > 60:
                                        logger.info(f"Dynamically quarantining old unplayable file: {recording_file.name}")
                                        self._quarantine_corrupted_files([recording_file])
                                except Exception as q_err:
                                    logger.warning(f"Failed to dynamically quarantine {recording_file}: {q_err}")
                                continue

                            # Parse timestamp robustly
                            timestamp = self._parse_timestamp_from_filename(recording_file.stem)
                            if not timestamp:
                                # If parsing fails, use file modification time
                                timestamp = datetime.fromtimestamp(recording_file.stat().st_mtime)
                                logger.debug(f"Used file mtime for timestamp: {recording_file.name}")

                            recording_info = {
                                "filename": recording_file.name,
                                "stream_id": stream_id,
                                "timestamp": timestamp.isoformat(),
                                "size_bytes": file_size,
                                "size_mb": round(file_size / (1024 * 1024), 2),
                                "path": str(recording_file)
                            }

                            all_recordings.append(recording_info)
                            logger.debug(f"Added recording: {recording_file.name} ({file_size} bytes)")

                        except Exception as e:
                            logger.warning(f"Error processing recording {recording_file}: {e}")
                            continue

            # Sort by timestamp (newest first)
            all_recordings.sort(key=lambda x: x['timestamp'], reverse=True)
            logger.info(f"Found {len(all_recordings)} valid recordings across all streams")
            return all_recordings

        except Exception as e:
            logger.error(f"Error getting all recordings: {e}")
            return []

    def _refresh_filesystem_cache(self):
        """Force refresh of filesystem cache to ensure we see latest files"""
        try:
            # On Windows, we can try to refresh the directory cache
            if os.name == 'nt':
                import ctypes
                # Force directory refresh
                for stream_dir in self.recordings_base_path.iterdir():
                    if stream_dir.is_dir():
                        try:
                            # Access the directory to refresh cache
                            list(stream_dir.iterdir())
                        except Exception:
                            pass
            else:
                # On Unix-like systems, sync filesystem
                try:
                    os.sync()
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error refreshing filesystem cache: {e}")

    def get_recording_path(self, stream_id: str, filename: str) -> Optional[Path]:
        """Get full path to a specific recording file"""
        try:
            stream_dir = self.recordings_base_path / stream_id
            recording_path = stream_dir / filename

            if recording_path.exists() and recording_path.suffix == '.mp4':
                return recording_path
            return None

        except Exception as e:
            logger.error(f"Error getting recording path for {stream_id}/{filename}: {e}")
            return None

    def get_recording_info(self, stream_id: str, filename: str) -> Optional[Dict]:
        """Get information about a specific recording"""
        try:
            recording_path = self.get_recording_path(stream_id, filename)
            if not recording_path:
                return None

            # Parse timestamp robustly
            timestamp = self._parse_timestamp_from_filename(recording_path.stem)

            # Get file size
            file_size = recording_path.stat().st_size

            return {
                "filename": filename,
                "stream_id": stream_id,
                "timestamp": timestamp.isoformat() if timestamp else None,
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2),
                "path": str(recording_path)
            }

        except Exception as e:
            logger.error(f"Error getting recording info for {stream_id}/{filename}: {e}")
            return None

    def get_status(self) -> Dict:
        """Get status of all recording processes"""
        # Count active recordings based on alive threads, not just active processes
        active_stream_ids = []
        for stream_id, thread in self.recording_threads.items():
            if thread.is_alive():
                active_stream_ids.append(stream_id)

        return {
            "active_recordings": len(active_stream_ids),
            "recording_threads": len(self.recording_threads),
            "stream_ids": active_stream_ids,
            "recordings_path": str(self.recordings_base_path),
            "cleanup_active": self.cleanup_thread.is_alive() if self.cleanup_thread else False
        }
