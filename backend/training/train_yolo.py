"""Train/fine-tune the VMS YOLO model from a HUMAN-REVIEWED dataset.

Example:
    python backend/training/train_yolo.py \
        --data backend/training_data/reviewed/vms.yaml \
        --model yolo26n.pt --epochs 80 --imgsz 960

The script intentionally refuses paths inside `review_queue`; hard examples are model proposals,
not ground truth. Label/review them first and export a normal Ultralytics dataset YAML.
"""

import argparse
import json
import os
from pathlib import Path

import torch
from ultralytics import YOLO


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "0"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune VMS YOLO on reviewed CCTV labels")
    parser.add_argument("--data", required=True, help="Ultralytics dataset YAML")
    parser.add_argument("--model", default=os.getenv("VMS_YOLO_MODEL", "yolo26n.pt"))
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--batch", type=int, default=-1, help="-1 lets Ultralytics select batch size")
    parser.add_argument("--device", default="auto", help="auto, cpu, 0, 0,1, mps, etc.")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--project", default="runs/vms_train")
    parser.add_argument("--name", default="vms_yolo_finetune")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def validate_dataset_path(data_path: Path):
    resolved = data_path.expanduser().resolve()
    if "review_queue" in {part.lower() for part in resolved.parts}:
        raise SystemExit(
            "Refusing to train directly from training_data/review_queue. "
            "Review/correct labels and export them under training_data/reviewed first."
        )
    if not resolved.exists():
        raise SystemExit(f"Dataset YAML not found: {resolved}")
    if resolved.suffix.lower() not in {".yaml", ".yml"}:
        raise SystemExit("--data must point to an Ultralytics YAML dataset definition")
    return resolved


def main():
    args = parse_args()
    data = validate_dataset_path(Path(args.data))
    device = resolve_device(args.device)

    model = YOLO(args.model)
    results = model.train(
        data=str(data),
        epochs=max(1, args.epochs),
        imgsz=max(320, args.imgsz),
        batch=args.batch,
        device=device,
        workers=max(0, args.workers),
        patience=max(0, args.patience),
        project=args.project,
        name=args.name,
        seed=args.seed,
        deterministic=True,
        cache=args.cache,
        resume=args.resume,
        plots=True,
        val=True,
    )

    save_dir = Path(getattr(results, "save_dir", Path(args.project) / args.name))
    metrics = getattr(results, "results_dict", {}) or {}
    summary = {
        "dataset": str(data),
        "base_model": args.model,
        "device": device,
        "save_dir": str(save_dir),
        "metrics": {str(k): float(v) if hasattr(v, "__float__") else str(v) for k, v in metrics.items()},
    }
    save_dir.mkdir(parents=True, exist_ok=True)
    with open(save_dir / "vms_training_summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))
    print("\nBefore deployment, run validation on a camera-separated holdout set and compare false alerts/hour.")


if __name__ == "__main__":
    main()
