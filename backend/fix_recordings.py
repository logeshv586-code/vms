"""
fix_recordings.py - Repair broken MP4 recordings with missing moov atoms.

This script scans recording directories for broken MP4 files (those missing
the moov atom that is required for playback) and attempts to repair them using
FFmpeg.  Two strategies are tried in order:

1. **Fast remux** – stream-copies audio/video and rewrites the container with
   a proper moov atom (`-movflags +faststart`).  This is lossless and very
   fast but may fail if the source streams themselves are damaged.
2. **Full transcode** – re-encodes video to H.264 (main profile, CRF 23) and
   audio to AAC.  Slower but can recover frames from partially-corrupt
   streams.

Usage
-----
    python fix_recordings.py                     # repair ./recordings
    python fix_recordings.py /path/to/recordings # repair custom path

The module also exposes ``async_repair_all_recordings()`` for integration into
a FastAPI application.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_executable_path(name: str) -> str:
    """Locate an FFmpeg / FFprobe executable.

    Search order:
      1. backend/ffmpeg-master-latest-win64-gpl-shared/bin/{name}.exe
      2. backend/ffmpeg/{name}.exe
      3. Fall back to bare ``name`` (relies on system PATH).
    """
    backend_dir = Path(__file__).parent
    local_paths = [
        backend_dir / "ffmpeg-master-latest-win64-gpl-shared" / "bin" / f"{name}.exe",
        backend_dir / "ffmpeg" / f"{name}.exe",
    ]
    for path in local_paths:
        if path.exists():
            logger.debug("Found %s at %s", name, path)
            return str(path)
    logger.debug("Using system %s", name)
    return name


def _is_file_in_use(filepath: Path) -> bool:
    """Heuristic check: try opening the file exclusively to see if another
    process (e.g. a recorder) currently holds a write lock."""
    try:
        with open(filepath, "r+b"):
            return False
    except (PermissionError, OSError):
        return True


def _free_disk_bytes(path: Path) -> int:
    """Return free disk space in bytes on the volume containing *path*."""
    return shutil.disk_usage(path).free


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def check_file_health(filepath: str, ffprobe_path: str) -> Dict[str, Any]:
    """Run ``ffprobe`` against *filepath* and return a health report.

    Returns a dict with keys:
        is_healthy  – True when the file has a valid moov atom and a non-zero
                      duration.
        has_moov    – True when ffprobe can read stream metadata (implies the
                      moov atom is present).
        duration    – Duration in seconds (float), or None on failure.
        error       – Error message string, or None when healthy.
    """
    result: Dict[str, Any] = {
        "is_healthy": False,
        "has_moov": False,
        "duration": None,
        "error": None,
    }

    fpath = Path(filepath)
    if not fpath.exists():
        result["error"] = "File does not exist"
        return result

    if fpath.stat().st_size == 0:
        result["error"] = "File is empty (0 bytes)"
        return result

    try:
        proc = subprocess.run(
            [
                ffprobe_path,
                "-v", "error",
                "-show_entries", "format=duration",
                "-show_entries", "stream=codec_type",
                "-of", "json",
                filepath,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            # Detect the classic moov-atom error
            if "moov atom not found" in stderr.lower():
                result["error"] = "Missing moov atom"
            elif "invalid data found" in stderr.lower():
                result["error"] = f"Invalid data: {stderr[:200]}"
            else:
                result["error"] = stderr[:300] if stderr else "ffprobe returned non-zero exit code"
            return result

        import json
        data = json.loads(proc.stdout)

        # Check for streams – their presence implies a readable moov atom.
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        duration_str = fmt.get("duration")

        if streams:
            result["has_moov"] = True

        if duration_str:
            try:
                result["duration"] = float(duration_str)
            except (ValueError, TypeError):
                pass

        # Consider healthy only when we have moov *and* a positive duration.
        if result["has_moov"] and result["duration"] and result["duration"] > 0:
            result["is_healthy"] = True
        elif not result["has_moov"]:
            result["error"] = "Missing moov atom (no streams found)"
        elif not result["duration"] or result["duration"] <= 0:
            result["error"] = "File has zero or unknown duration"

    except subprocess.TimeoutExpired:
        result["error"] = "ffprobe timed out (file may be very large or corrupt)"
    except FileNotFoundError:
        result["error"] = f"ffprobe not found at '{ffprobe_path}'"
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Unexpected error: {exc}"

    return result


# ---------------------------------------------------------------------------
# Repair logic
# ---------------------------------------------------------------------------

def repair_recording(
    filepath: str,
    ffmpeg_path: str,
    ffprobe_path: str,
) -> Dict[str, Any]:
    """Attempt to repair a single MP4 recording.

    Returns a dict with keys:
        success     – True on successful repair.
        method      – ``"remux"`` or ``"transcode"`` or None.
        error       – Error description on failure, else None.
        original_size – Size of the original file in bytes.
        repaired_size – Size of the repaired file in bytes (0 on failure).
    """
    result: Dict[str, Any] = {
        "success": False,
        "method": None,
        "error": None,
        "original_size": 0,
        "repaired_size": 0,
    }

    src = Path(filepath)
    if not src.exists():
        result["error"] = "Source file does not exist"
        return result

    result["original_size"] = src.stat().st_size

    # Safety: skip files currently being written by a recorder.
    if _is_file_in_use(src):
        result["error"] = "File is currently in use (possibly still being recorded)"
        return result

    # Ensure we have enough free space (need at least the file's size).
    free = _free_disk_bytes(src.parent)
    if free < result["original_size"] * 2:
        result["error"] = (
            f"Insufficient disk space: {free / 1_048_576:.1f} MiB free, "
            f"need ~{result['original_size'] * 2 / 1_048_576:.1f} MiB"
        )
        return result

    # We write the temp file in the *same directory* so the final rename is
    # an atomic same-filesystem operation.
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=str(src.parent))
    os.close(tmp_fd)

    try:
        # ---- Strategy 1: fast remux ----
        logger.info("Attempting fast remux for %s", filepath)
        remux_ok = _run_ffmpeg(
            ffmpeg_path,
            [
                "-y",
                "-i", filepath,
                "-c", "copy",
                "-movflags", "+faststart",
                tmp_path,
            ],
            timeout=120,
        )

        if remux_ok:
            health = check_file_health(tmp_path, ffprobe_path)
            if health["is_healthy"]:
                _swap_files(src, Path(tmp_path))
                result["success"] = True
                result["method"] = "remux"
                result["repaired_size"] = src.stat().st_size
                logger.info("Fast remux succeeded for %s", filepath)
                return result
            else:
                logger.warning(
                    "Remuxed file is still unhealthy (%s); falling back to transcode",
                    health.get("error"),
                )

        # ---- Strategy 2: full transcode ----
        logger.info("Attempting full transcode for %s", filepath)

        # Recreate temp file (the previous one may be partial / corrupt)
        _safe_remove(Path(tmp_path))
        tmp_fd2, tmp_path = tempfile.mkstemp(suffix=".mp4", dir=str(src.parent))
        os.close(tmp_fd2)

        transcode_ok = _run_ffmpeg(
            ffmpeg_path,
            [
                "-y",
                "-i", filepath,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-profile:v", "main",
                "-pix_fmt", "yuv420p",
                "-color_range", "tv",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ar", "44100",
                "-movflags", "+faststart",
                tmp_path,
            ],
            timeout=600,
        )

        if transcode_ok:
            health = check_file_health(tmp_path, ffprobe_path)
            if health["is_healthy"]:
                _swap_files(src, Path(tmp_path))
                result["success"] = True
                result["method"] = "transcode"
                result["repaired_size"] = src.stat().st_size
                logger.info("Full transcode succeeded for %s", filepath)
                return result
            else:
                result["error"] = (
                    f"Transcoded file is still unhealthy: {health.get('error')}"
                )
        else:
            result["error"] = "Both remux and transcode failed"

    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Unexpected error during repair: {exc}"
        logger.exception("Unexpected error repairing %s", filepath)
    finally:
        _safe_remove(Path(tmp_path))

    return result


def _run_ffmpeg(ffmpeg_path: str, args: List[str], timeout: int = 120) -> bool:
    """Run ffmpeg with *args* and return True on success."""
    cmd = [ffmpeg_path] + args
    logger.debug("Running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            logger.warning("ffmpeg failed (rc=%d): %s", proc.returncode, proc.stderr[:500])
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timed out after %d s", timeout)
        return False
    except FileNotFoundError:
        logger.error("ffmpeg not found at '%s'", ffmpeg_path)
        return False


def _swap_files(original: Path, repaired: Path) -> None:
    """Replace *original* with *repaired* safely.

    A backup of the original is kept briefly so we can restore on error.
    """
    backup = original.with_suffix(".mp4.bak")
    try:
        original.rename(backup)
        repaired.rename(original)
        # Successfully swapped – remove the backup.
        _safe_remove(backup)
    except Exception:
        # If the rename failed, try to restore the backup.
        if backup.exists() and not original.exists():
            backup.rename(original)
        raise


def _safe_remove(path: Path) -> None:
    """Delete *path* if it exists, swallowing errors."""
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        logger.debug("Could not remove %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Batch repair
# ---------------------------------------------------------------------------

def repair_all_recordings(recordings_base_path: str) -> Dict[str, Any]:
    """Scan *recordings_base_path* for broken MP4 files and repair them.

    Returns a summary dict::

        {
            "total": int,
            "healthy": int,
            "repaired": int,
            "failed": int,
            "skipped": int,
            "details": [ ... per-file dicts ... ],
        }
    """
    base = Path(recordings_base_path)
    ffmpeg_path = get_executable_path("ffmpeg")
    ffprobe_path = get_executable_path("ffprobe")

    summary: Dict[str, Any] = {
        "total": 0,
        "healthy": 0,
        "repaired": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    if not base.exists():
        logger.error("Recordings directory does not exist: %s", base)
        summary["error"] = f"Recordings directory not found: {base}"
        return summary

    logger.info("Starting repair scan in %s", base)
    logger.info("Using ffmpeg : %s", ffmpeg_path)
    logger.info("Using ffprobe: %s", ffprobe_path)

    # Collect MP4 files across all stream sub-directories.
    mp4_files: List[Path] = []
    for stream_dir in sorted(base.iterdir()):
        if not stream_dir.is_dir():
            continue
        # Skip hidden / special dirs
        if stream_dir.name.startswith(".") or stream_dir.name == "quarantine":
            continue
        for f in sorted(stream_dir.glob("*.mp4")):
            # Skip intermediate ".converted.mp4" scratch files.
            if f.name.endswith(".converted.mp4"):
                continue
            mp4_files.append(f)

    summary["total"] = len(mp4_files)
    logger.info("Found %d MP4 file(s) to inspect", len(mp4_files))

    for idx, mp4 in enumerate(mp4_files, 1):
        rel = mp4.relative_to(base)
        detail: Dict[str, Any] = {
            "file": str(rel),
            "status": "unknown",
            "method": None,
            "error": None,
        }

        logger.info("[%d/%d] Checking %s …", idx, summary["total"], rel)

        # ---- Health check ----
        health = check_file_health(str(mp4), ffprobe_path)

        if health["is_healthy"]:
            detail["status"] = "healthy"
            summary["healthy"] += 1
            logger.info("  ✓ Healthy (duration=%.1fs)", health.get("duration", 0) or 0)
            summary["details"].append(detail)
            continue

        logger.warning("  ✗ Broken – %s", health.get("error", "unknown issue"))

        # ---- Attempt repair ----
        repair = repair_recording(str(mp4), ffmpeg_path, ffprobe_path)

        if repair["success"]:
            detail["status"] = "repaired"
            detail["method"] = repair["method"]
            summary["repaired"] += 1
            logger.info(
                "  ✓ Repaired via %s (%d → %d bytes)",
                repair["method"],
                repair["original_size"],
                repair["repaired_size"],
            )
        else:
            detail["status"] = "failed"
            detail["error"] = repair.get("error")
            summary["failed"] += 1
            logger.error("  ✗ Repair failed – %s", repair.get("error"))
            
            # Quarantine the file
            try:
                quarantine_dir = base / "quarantine"
                quarantine_dir.mkdir(exist_ok=True)
                timestamp = int(time.time())
                clean_stem = mp4.stem
                if "_corrupted_" in clean_stem:
                    clean_stem = clean_stem.split("_corrupted_")[0]
                quarantine_name = f"{clean_stem}_corrupted_{timestamp}.mp4"
                quarantine_path = quarantine_dir / quarantine_name
                mp4.rename(quarantine_path)
                logger.info("  → Quarantined unrecoverable file to %s", quarantine_path)
            except Exception as e:
                logger.error("  → Failed to quarantine file: %s", e)

        summary["details"].append(detail)

    logger.info(
        "Repair scan complete – total=%d healthy=%d repaired=%d failed=%d skipped=%d",
        summary["total"],
        summary["healthy"],
        summary["repaired"],
        summary["failed"],
        summary["skipped"],
    )
    return summary


# ---------------------------------------------------------------------------
# Async wrapper (for FastAPI integration)
# ---------------------------------------------------------------------------

async def async_repair_all_recordings(recordings_base_path: str) -> Dict[str, Any]:
    """Async wrapper around :func:`repair_all_recordings`.

    Runs the (blocking) repair pipeline in a background thread so it does not
    block the FastAPI event loop.
    """
    return await asyncio.to_thread(repair_all_recordings, recordings_base_path)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # When invoked directly, configure root logger to print to stdout.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if len(sys.argv) > 1:
        recordings_dir = sys.argv[1]
    else:
        recordings_dir = str(Path(__file__).parent / "recordings")

    print(f"\n{'='*60}")
    print(f"  MP4 Recording Repair Tool")
    print(f"{'='*60}")
    print(f"  Recordings path : {recordings_dir}")
    print(f"  FFmpeg           : {get_executable_path('ffmpeg')}")
    print(f"  FFprobe          : {get_executable_path('ffprobe')}")
    print(f"{'='*60}\n")

    start = time.time()
    summary = repair_all_recordings(recordings_dir)
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Total files  : {summary['total']}")
    print(f"  Healthy      : {summary['healthy']}")
    print(f"  Repaired     : {summary['repaired']}")
    print(f"  Failed       : {summary['failed']}")
    print(f"  Skipped      : {summary['skipped']}")
    print(f"  Elapsed      : {elapsed:.1f}s")
    print(f"{'='*60}\n")

    if summary["failed"] > 0:
        print("Failed files:")
        for d in summary["details"]:
            if d["status"] == "failed":
                print(f"  • {d['file']} – {d.get('error', 'unknown')}")
        print()

    sys.exit(1 if summary["failed"] > 0 else 0)
