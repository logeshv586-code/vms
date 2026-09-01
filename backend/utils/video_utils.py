#!/usr/bin/env python3
"""
Consolidated Video Utilities for VMS

Provides comprehensive utilities for:
1. Video inspection (ffprobe metadata, codec assessment, and pixel format checks)
2. Video conversion (browser-compatible H.264 MP4 conversion, .tmp resolution)
3. Video validation (archive file integrity sweeps and playback audits)

Acts as a drop-in unified CLI replacement for duplicate script files.
"""

import os
import sys
import json
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class VideoInspector:
    """Utility class for inspecting video file codecs and formats using ffprobe"""

    @staticmethod
    def inspect_video_codecs(file_path: Path) -> Optional[Dict]:
        """
        Inspect video file codecs using ffprobe.
        
        Returns:
            Dictionary containing codec information or None if inspection fails.
        """
        try:
            if not file_path.exists():
                logger.error(f"Video file does not exist: {file_path}")
                return None

            ffprobe_cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]

            result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"ffprobe failed for {file_path}: {result.stderr}")
                return None

            probe_data = json.loads(result.stdout)

            video_codec = None
            audio_codec = None
            pix_fmt = None
            color_range = None
            width = 0
            height = 0
            frame_rate = 0.0

            for stream in probe_data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_codec = stream.get('codec_name')
                    pix_fmt = stream.get('pix_fmt')
                    color_range = stream.get('color_range')
                    width = int(stream.get('width', 0))
                    height = int(stream.get('height', 0))
                    
                    # Parse frame rate
                    r_frame_rate = stream.get('r_frame_rate', '0/1')
                    if '/' in r_frame_rate:
                        num, den = r_frame_rate.split('/')
                        if int(den) > 0:
                            frame_rate = float(num) / float(den)
                elif stream.get('codec_type') == 'audio':
                    audio_codec = stream.get('codec_name')

            container = probe_data.get('format', {}).get('format_name', '').split(',')[0]

            # Standard web compatibility checks
            compatible_video_codecs = {'h264', 'hevc', 'h265', 'mpeg4', 'avc'}
            compatible_audio_codecs = {'aac', 'mp3', 'ac3'}

            video_compatible = video_codec in compatible_video_codecs if video_codec else True
            audio_compatible = audio_codec in compatible_audio_codecs if audio_codec else True
            
            is_mp4_compatible = video_compatible and audio_compatible
            needs_conversion = not is_mp4_compatible and container != 'mp4'

            # Flag problematic codecs in MP4 container
            if container == 'mp4':
                problematic_video = video_codec in {'vp8', 'vp9', 'av1'}
                problematic_audio = audio_codec in {'opus', 'vorbis'}
                if problematic_video or problematic_audio:
                    needs_conversion = True
                    is_mp4_compatible = False

            # Check for problematic pixel formats or color ranges
            if pix_fmt in ['yuvj420p', 'yuvj422p', 'yuvj444p'] or color_range == 'pc':
                is_mp4_compatible = False
                needs_conversion = True

            return {
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'video_codec': video_codec,
                'audio_codec': audio_codec,
                'pix_fmt': pix_fmt,
                'color_range': color_range,
                'width': width,
                'height': height,
                'frame_rate': frame_rate,
                'container': container,
                'compatible_with_mp4': is_mp4_compatible,
                'needs_conversion': needs_conversion,
                'duration': float(probe_data.get('format', {}).get('duration', 0)),
                'bit_rate': int(probe_data.get('format', {}).get('bit_rate', 0)),
                'streams': probe_data.get('streams', []),
                'format': probe_data.get('format', {})
            }

        except Exception as e:
            logger.error(f"Error inspecting codecs for {file_path}: {e}")
            return None

    @staticmethod
    def get_video_info(file_path: Path) -> Optional[Dict]:
        """Legacy helper alias matching VideoValidator.get_video_info interface."""
        return VideoInspector.inspect_video_codecs(file_path)

    @staticmethod
    def needs_pixel_format_fix(video_info: Dict) -> bool:
        """Check if video needs pixel format or color range conversion"""
        if not video_info:
            return False
        
        pix_fmt = video_info.get('pix_fmt', '')
        color_range = video_info.get('color_range', '')

        # Check for problematic pixel formats
        if pix_fmt in ['yuvj420p', 'yuvj422p', 'yuvj444p']:
            logger.info(f"Found problematic pixel format: {pix_fmt}")
            return True
            
        # Check for PC color range (should be tv/limited range for browser)
        if color_range == 'pc':
            logger.info("Found PC color range - needs conversion")
            return True

        return False


class VideoConverter:
    """Utility class for converting videos to browser-compatible H.264 formats"""

    @staticmethod
    def convert_to_mp4_compatible(input_path: Path, output_path: Path) -> bool:
        """
        Convert video file to browser-compatible MP4 format.
        
        Uses libx264 baseline/main profile, standard yuv420p color format, 
        aac audio, and faststart parameters for web streaming.
        """
        try:
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', str(input_path),
                # Video encoding for maximum browser compatibility
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-profile:v', 'main',
                '-pix_fmt', 'yuv420p',  # Force standard browser pixel format
                '-color_range', 'tv',  # Force TV/limited range
                # Audio encoding
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ar', '44100',
                # Container settings
                '-f', 'mp4',
                '-movflags', '+faststart',
                '-avoid_negative_ts', 'make_zero',
                '-y',  # Overwrite output
                str(output_path)
            ]

            logger.info(f"Converting {input_path.name} to MP4-compatible format: {output_path.name}")
            logger.debug(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

            result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.info(f"Successfully converted {input_path.name} to {output_path.name}")
                return True
            else:
                logger.error(f"FFmpeg conversion failed for {input_path.name}: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error converting {input_path} to MP4: {e}")
            return False

    @staticmethod
    def convert_all_tmp_files(recordings_dir: Path, dry_run: bool = False) -> Dict:
        """Scan and convert all .tmp recording files in a directory to .mp4"""
        stats = {'total_found': 0, 'converted': 0, 'failed': 0, 'skipped': 0}
        
        if not recordings_dir.exists():
            logger.error(f"Recordings directory not found: {recordings_dir}")
            return stats

        tmp_files = list(recordings_dir.rglob("*.tmp"))
        stats['total_found'] = len(tmp_files)
        logger.info(f"Found {len(tmp_files)} .tmp files to convert")

        if dry_run:
            logger.info("DRY RUN MODE - showing what would be converted:")
            for tmp_file in tmp_files:
                logger.info(f"  - Would convert: {tmp_file} -> {tmp_file.with_suffix('.mp4')}")
            return stats

        for tmp_file in tmp_files:
            mp4_file = tmp_file.with_suffix('.mp4')
            if mp4_file.exists():
                logger.info(f"MP4 already exists for {tmp_file.name}, skipping")
                stats['skipped'] += 1
                continue

            if tmp_file.stat().st_size < 1024:
                logger.warning(f"Skipping tiny/empty file: {tmp_file.name}")
                stats['skipped'] += 1
                continue

            if VideoConverter.convert_to_mp4_compatible(tmp_file, mp4_file):
                stats['converted'] += 1
                try:
                    tmp_file.unlink()
                    logger.info(f"Removed original .tmp file: {tmp_file.name}")
                except Exception as e:
                    logger.warning(f"Could not delete .tmp file: {e}")
            else:
                stats['failed'] += 1

        return stats

    @staticmethod
    def fix_recordings_compatibility(recordings_dir: Path, dry_run: bool = False) -> Dict:
        """Scan and fix pixel format / color range issues for all MP4 recordings"""
        stats = {'total_checked': 0, 'needs_fix': 0, 'fixed': 0, 'failed': 0, 'skipped': 0}
        
        if not recordings_dir.exists():
            logger.error(f"Recordings directory not found: {recordings_dir}")
            return stats

        mp4_files = []
        for file in recordings_dir.rglob("*.mp4"):
            if 'quarantine' not in str(file) and not file.name.endswith('.backup'):
                mp4_files.append(file)

        stats['total_checked'] = len(mp4_files)
        logger.info(f"Scanning {len(mp4_files)} MP4 files for browser compatibility...")

        for mp4_file in mp4_files:
            info = VideoInspector.inspect_video_codecs(mp4_file)
            if not info:
                continue

            if VideoInspector.needs_pixel_format_fix(info):
                stats['needs_fix'] += 1
                
                if dry_run:
                    logger.info(f"DRY RUN - Would fix compatibility for: {mp4_file}")
                    continue

                backup_path = mp4_file.with_suffix('.mp4.backup')
                if backup_path.exists():
                    logger.info(f"Backup already exists for {mp4_file.name}, skipping")
                    stats['skipped'] += 1
                    continue

                try:
                    shutil.copy2(mp4_file, backup_path)
                    logger.info(f"Created backup: {backup_path.name}")
                except Exception as e:
                    logger.error(f"Failed to create backup for {mp4_file.name}: {e}")
                    stats['failed'] += 1
                    continue

                # Temporary conversion target
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                    temp_path = Path(temp_file.name)

                try:
                    if VideoConverter.convert_to_mp4_compatible(backup_path, temp_path):
                        shutil.move(str(temp_path), str(mp4_file))
                        stats['fixed'] += 1
                        logger.info(f"Successfully fixed pixel format for {mp4_file.name}")
                    else:
                        stats['failed'] += 1
                except Exception as e:
                    logger.error(f"Failed during file swaps: {e}")
                    stats['failed'] += 1
                finally:
                    if temp_path.exists():
                        temp_path.unlink()

        return stats


class VideoValidator:
    """Utility class for validating recording file integrity and structure"""

    @staticmethod
    def validate_recording_file(file_path: Path) -> Dict:
        """Validate a single recording file's playability and properties"""
        result = {
            'file_path': str(file_path),
            'exists': file_path.exists(),
            'is_valid': False,
            'is_playable': False,
            'info': None,
            'recommendations': []
        }

        if not result['exists']:
            result['recommendations'].append("File does not exist")
            return result

        info = VideoInspector.inspect_video_codecs(file_path)
        result['info'] = info

        if info:
            has_video = info['width'] > 0 and info['height'] > 0
            is_valid = info['duration'] > 0 and has_video
            
            result['is_valid'] = is_valid
            result['is_playable'] = is_valid and info['compatible_with_mp4']

            if not is_valid:
                result['recommendations'].append("File appears corrupted or empty (no video stream / zero duration)")
            if not info['compatible_with_mp4']:
                result['recommendations'].append(f"Incompatible video properties: codec={info['video_codec']}, pix_fmt={info['pix_fmt']}, range={info['color_range']}")
                result['recommendations'].append("Recommendation: Run converter to format as browser-compatible MP4")
        else:
            result['recommendations'].append("Unable to parse file metadata - may be severely corrupted")

        return result

    @staticmethod
    def validate_recordings_directory(recordings_path: Path) -> Dict:
        """Validate all recordings inside a directory structure"""
        results = {
            'directory': str(recordings_path),
            'total_files': 0,
            'valid_files': 0,
            'invalid_files': 0,
            'file_results': []
        }

        if not recordings_path.exists():
            logger.error(f"Recordings directory does not exist: {recordings_path}")
            return results

        mp4_files = list(recordings_path.rglob("*.mp4"))
        results['total_files'] = len(mp4_files)

        for file in mp4_files:
            file_res = VideoValidator.validate_recording_file(file)
            results['file_results'].append(file_res)
            
            if file_res['is_valid']:
                results['valid_files'] += 1
            else:
                results['invalid_files'] += 1

        return results


def main():
    """CLI handler supporting backwards-compatible properties for all script actions"""
    parser = argparse.ArgumentParser(description='VMS Consolidated Video Utility')
    
    subparsers = parser.add_subparsers(dest='command', help='Utility commands')
    
    # Inspect Command
    inspect_parser = subparsers.add_parser('inspect', help='Inspect video codecs')
    inspect_parser.add_argument('path', type=Path, help='Path to video file')

    # Convert Command
    convert_parser = subparsers.add_parser('convert', help='Convert video to MP4 compatible')
    convert_parser.add_argument('input', type=Path, help='Input file')
    convert_parser.add_argument('output', type=Path, help='Output file')

    # Fix Command
    fix_parser = subparsers.add_parser('fix', help='Fix video compatibility/pixel formats')
    fix_parser.add_argument('--recordings-dir', type=Path, default=Path('recordings'), help='Path to recordings directory')
    fix_parser.add_argument('--dry-run', action='store_true', help='Dry run scan only')

    # Convert Tmp Command
    tmp_parser = subparsers.add_parser('convert-tmp', help='Convert all temporary recording segments to MP4')
    tmp_parser.add_argument('--recordings-dir', type=Path, default=Path('recordings'), help='Recordings path')
    tmp_parser.add_argument('--dry-run', action='store_true', help='Dry run scan only')

    # Validate Command
    validate_parser = subparsers.add_parser('validate', help='Validate video files')
    validate_parser.add_argument('path', type=Path, help='File or directory to validate')

    # Parse arguments
    args = parser.parse_args()

    # Default fallback: if no command is specified, check the legacy CLI actions
    if not args.command:
        # Match legacy video_validator / validate_recordings pattern
        # If we have a single argument that is a path
        print("VMS Video Utility Console. Specify command (inspect, convert, fix, convert-tmp, validate) or use --help.")
        return 1

    if args.command == 'inspect':
        res = VideoInspector.inspect_video_codecs(args.path)
        print(json.dumps(res, indent=2) if res else "Failed to inspect file.")
    
    elif args.command == 'convert':
        success = VideoConverter.convert_to_mp4_compatible(args.input, args.output)
        print("Conversion successful!" if success else "Conversion failed.")
        return 0 if success else 1
    
    elif args.command == 'fix':
        stats = VideoConverter.fix_recordings_compatibility(args.recordings_dir, args.dry_run)
        print(json.dumps(stats, indent=2))
        
    elif args.command == 'convert-tmp':
        stats = VideoConverter.convert_all_tmp_files(args.recordings_dir, args.dry_run)
        print(json.dumps(stats, indent=2))
        
    elif args.command == 'validate':
        if args.path.is_file():
            res = VideoValidator.validate_recording_file(args.path)
            print(json.dumps(res, indent=2))
        else:
            res = VideoValidator.validate_recordings_directory(args.path)
            print(f"Directory sweep validation of {args.path.name}:")
            print(f"Total checked: {res['total_files']}, Valid: {res['valid_files']}, Invalid: {res['invalid_files']}")
            if res['invalid_files'] > 0:
                print("Invalid files detected:")
                for file_res in res['file_results']:
                    if not file_res['is_valid']:
                        print(f"  - {file_res['file_path']} -> Recommendations: {file_res['recommendations']}")

    return 0


if __name__ == '__main__':
    import argparse
    sys.exit(main())
