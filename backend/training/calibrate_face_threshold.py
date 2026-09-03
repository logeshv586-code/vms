"""Calibrate the face-recognition distance threshold from labelled validation pairs.

Input JSON must be a list (or {"pairs": [...]}) with records such as:
    {"distance": 0.41, "same_identity": true}
    {"distance": 0.63, "same_identity": false}

Generate the distances from your real cameras using the same embedding backend used in
production. This script chooses a threshold using labelled evidence; it does not invent a
production tolerance from generic benchmark data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_pairs(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("pairs", [])
    if not isinstance(data, list):
        raise SystemExit("Input must be a JSON list or an object containing a 'pairs' list")

    pairs = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        try:
            distance = float(item["distance"])
        except (KeyError, TypeError, ValueError):
            continue
        same = item.get("same_identity")
        if not isinstance(same, bool):
            continue
        if distance < 0:
            continue
        pairs.append((distance, same))

    positives = sum(1 for _, same in pairs if same)
    negatives = len(pairs) - positives
    if positives < 5 or negatives < 5:
        raise SystemExit(
            f"Need at least 5 genuine and 5 impostor labelled pairs; got {positives} and {negatives}."
        )
    return pairs


def metrics(pairs, threshold):
    tp = fp = tn = fn = 0
    for distance, same in pairs:
        predicted_same = distance <= threshold
        if predicted_same and same:
            tp += 1
        elif predicted_same and not same:
            fp += 1
        elif not predicted_same and not same:
            tn += 1
        else:
            fn += 1

    tpr = tp / (tp + fn) if tp + fn else 0.0
    tnr = tn / (tn + fp) if tn + fp else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tpr
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    far = fp / (fp + tn) if fp + tn else 0.0
    frr = fn / (fn + tp) if fn + tp else 0.0
    balanced_accuracy = (tpr + tnr) / 2.0
    return {
        "threshold": threshold,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_accept_rate": far,
        "false_reject_rate": frr,
        "balanced_accuracy": balanced_accuracy,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Calibrate VMS face distance threshold")
    parser.add_argument("--pairs", required=True, help="Labelled JSON distance pairs")
    parser.add_argument("--objective", choices=("balanced_accuracy", "f1"), default="balanced_accuracy")
    parser.add_argument("--max-far", type=float, default=None, help="Optional maximum false-accept rate")
    parser.add_argument("--output", default="face_threshold_calibration.json")
    return parser.parse_args()


def main():
    args = parse_args()
    pairs_path = Path(args.pairs).expanduser().resolve()
    if not pairs_path.exists():
        raise SystemExit(f"Pairs file not found: {pairs_path}")
    pairs = load_pairs(pairs_path)

    distances = sorted({distance for distance, _ in pairs})
    candidates = [max(0.0, distances[0] - 1e-6)]
    candidates.extend((left + right) / 2.0 for left, right in zip(distances, distances[1:]))
    candidates.append(distances[-1] + 1e-6)

    evaluated = [metrics(pairs, threshold) for threshold in candidates]
    if args.max_far is not None:
        max_far = max(0.0, min(1.0, args.max_far))
        constrained = [item for item in evaluated if item["false_accept_rate"] <= max_far]
        if constrained:
            evaluated = constrained

    selected = max(
        evaluated,
        key=lambda item: (
            item[args.objective],
            -item["false_accept_rate"],
            -item["false_reject_rate"],
        ),
    )

    output = {
        "schema_version": 1,
        "pairs_file": str(pairs_path),
        "pair_count": len(pairs),
        "genuine_pairs": sum(1 for _, same in pairs if same),
        "impostor_pairs": sum(1 for _, same in pairs if not same),
        "objective": args.objective,
        "max_far_constraint": args.max_far,
        "recommended_recognition_tolerance": selected["threshold"],
        "metrics": selected,
        "deployment": {
            "environment_variable": "VMS_FACE_RECOGNITION_TOLERANCE",
            "value": f"{selected['threshold']:.6f}",
        },
    }

    output_path = Path(args.output).expanduser().resolve()
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    print(f"\nSaved calibration report: {output_path}")


if __name__ == "__main__":
    main()
