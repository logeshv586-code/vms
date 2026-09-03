"""Run a repeatable VMS runtime soak/health benchmark against a live backend.

This tool does not need model weights locally; it exercises the running VMS API and records
availability, request latency, active streams, detection activity and optional NVIDIA GPU memory.
It is intended for the user's actual camera/GPU machine where meaningful soak metrics exist.

Example:
    python backend/tools/validate_runtime.py --duration 900 --interval 5 \
        --output runtime_validation.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen


def fetch_json(base_url: str, endpoint: str, timeout: float = 5.0):
    started = time.perf_counter()
    request = Request(base_url.rstrip("/") + endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        return body, (time.perf_counter() - started) * 1000.0, None
    except Exception as exc:
        return None, (time.perf_counter() - started) * 1000.0, str(exc)


def gpu_snapshot():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        rows = []
        for line in result.stdout.strip().splitlines():
            parts = [item.strip() for item in line.split(",")]
            if len(parts) >= 5:
                rows.append(
                    {
                        "name": parts[0],
                        "memory_used_mb": float(parts[1]),
                        "memory_total_mb": float(parts[2]),
                        "utilization_percent": float(parts[3]),
                        "temperature_c": float(parts[4]),
                    }
                )
        return rows or None
    except Exception:
        return None


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def parse_args():
    parser = argparse.ArgumentParser(description="Soak-test a live VMS backend")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--duration", type=float, default=300.0, help="seconds")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between samples")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--output", default="vms_runtime_validation.json")
    parser.add_argument("--fail-on-errors", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    duration = max(10.0, args.duration)
    interval = max(1.0, args.interval)
    started_wall = datetime.now(timezone.utc)
    deadline = time.monotonic() + duration

    endpoint_latencies = {}
    errors = []
    samples = []
    observed_streams = set()
    detection_samples = {}
    gpu_samples = []

    sample_number = 0
    while time.monotonic() < deadline:
        sample_number += 1
        sample = {
            "sample": sample_number,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "endpoints": {},
        }

        for endpoint in ("/api/health", "/api/ai/status", "/api/stream_health", "/api/streams"):
            body, latency, error = fetch_json(args.base_url, endpoint, args.timeout)
            endpoint_latencies.setdefault(endpoint, []).append(latency)
            sample["endpoints"][endpoint] = {"latency_ms": round(latency, 2), "ok": error is None}
            if error:
                errors.append({"at": sample["captured_at"], "endpoint": endpoint, "error": error})
                continue

            if endpoint == "/api/streams" and isinstance(body, dict):
                streams = body.get("streams", {})
                if isinstance(streams, dict):
                    observed_streams.update(streams.keys())

        for stream_id in sorted(observed_streams):
            endpoint = f"/api/stream/detections/{quote(stream_id, safe='')}"
            body, latency, error = fetch_json(args.base_url, endpoint, args.timeout)
            endpoint_latencies.setdefault("/api/stream/detections/{stream}", []).append(latency)
            if error:
                errors.append({"at": sample["captured_at"], "endpoint": endpoint, "error": error})
                continue
            if isinstance(body, dict):
                count = len(body.get("detections", []) or [])
                detection_samples.setdefault(stream_id, []).append(count)

        gpu = gpu_snapshot()
        if gpu:
            gpu_samples.append(gpu)
            sample["gpu"] = gpu

        samples.append(sample)
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(interval, remaining))

    latency_summary = {}
    for endpoint, values in endpoint_latencies.items():
        latency_summary[endpoint] = {
            "samples": len(values),
            "mean_ms": round(statistics.fmean(values), 2) if values else None,
            "p50_ms": round(percentile(values, 0.50), 2) if values else None,
            "p95_ms": round(percentile(values, 0.95), 2) if values else None,
            "max_ms": round(max(values), 2) if values else None,
        }

    gpu_summary = None
    if gpu_samples:
        flattened = [row for snapshot in gpu_samples for row in snapshot]
        gpu_summary = {
            "sample_count": len(gpu_samples),
            "max_memory_used_mb": max(row["memory_used_mb"] for row in flattened),
            "max_utilization_percent": max(row["utilization_percent"] for row in flattened),
            "max_temperature_c": max(row["temperature_c"] for row in flattened),
        }

    result = {
        "schema_version": 1,
        "started_at": started_wall.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "requested_duration_seconds": duration,
        "sample_interval_seconds": interval,
        "sample_count": len(samples),
        "observed_streams": sorted(observed_streams),
        "error_count": len(errors),
        "errors": errors[-100:],
        "latency": latency_summary,
        "detections": {
            stream_id: {
                "samples": len(values),
                "non_empty_samples": sum(1 for value in values if value > 0),
                "max_detections": max(values) if values else 0,
            }
            for stream_id, values in detection_samples.items()
        },
        "gpu": gpu_summary,
    }

    output = Path(args.output).expanduser().resolve()
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nSaved runtime validation report: {output}")

    if args.fail_on_errors and errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
