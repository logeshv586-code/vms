# VMS Realtime Detection Training & Validation Workflow

The production camera feed should **not** train YOLO directly from its own predictions. That creates a feedback loop where false positives become labels and accuracy degrades.

## 1. Collect hard examples from real cameras

Enable collection only on an approved test/development deployment:

```bash
VMS_COLLECT_HARD_EXAMPLES=true
VMS_HARD_EXAMPLE_INTERVAL_SECONDS=10
VMS_HARD_EXAMPLE_MAX_PER_DAY=500
VMS_HARD_EXAMPLE_RETENTION_DAYS=30
VMS_HARD_EXAMPLE_MAX_STORAGE_GB=20
```

The runtime saves uncertain frames and post-Tier-2 proposal metadata under:

```text
backend/training_data/review_queue/YYYYMMDD/<camera>/
```

Each `.json` sidecar is marked:

```json
{
  "review_status": "pending",
  "ground_truth": null,
  "proposal_only": true
}
```

Do not use those proposal labels as ground truth. Retention cleanup is automatic and bounded by both age and total queue storage.

## 2. Human review and annotation

Review the frames and create/correct bounding boxes with the class names required by the VMS deployment. Keep cameras separated when creating train/validation/test splits so nearly identical frames from one camera do not leak into both training and validation.

Recommended split:

- train: 70%
- validation: 20%
- final camera-separated test: 10%

Include difficult negatives: shadows, reflections, empty scenes, occlusion, rain, night views, crowds, partial bodies, parked vehicles, bags carried normally, people sitting/lying normally, and non-threatening hand gestures.

## 3. Export an Ultralytics dataset

Place the reviewed dataset outside `review_queue`, for example:

```text
backend/training_data/reviewed/v1/
  images/train/
  images/val/
  images/test/
  labels/train/
  labels/val/
  labels/test/
  vms.yaml
```

Example `vms.yaml`:

```yaml
path: backend/training_data/reviewed/v1
train: images/train
val: images/val
test: images/test
names:
  0: person
  1: car
  2: motorcycle
  3: bus
  4: truck
  5: backpack
  6: handbag
  7: suitcase
  8: cell phone
```

Extend the class list only for classes that have enough reviewed examples. Security behaviors such as fighting, collapse, snatching, harassment, loitering, and intrusion should not be represented as single-frame object labels unless a dedicated, correctly labelled action model is being trained. They remain temporal/semantic rules in the current architecture.

## 4. Fine-tune YOLO

```bash
python backend/training/train_yolo.py \
  --data backend/training_data/reviewed/v1/vms.yaml \
  --model yolo26n.pt \
  --epochs 80 \
  --imgsz 960 \
  --device auto
```

The script refuses to train directly from any path containing `review_queue`.

## 5. Validate before deployment

Do not promote a model based only on training mAP. Compare it to the currently deployed model on the same held-out camera clips and record at least:

- precision and recall per class
- mAP50 and mAP50-95
- missed-event rate
- false alerts per camera-hour
- tracker ID switches
- night/day performance separately
- small/occluded-object performance
- end-to-end latency and processed FPS

For behavior rules, separately score event-level precision/recall on timestamped clips. Gemma should be evaluated as a verifier: correct validation/rejection rate, timeout rate, and false-confirmation rate.

### Live multi-camera soak / GPU benchmark

Run this on the actual VMS machine while the configured cameras are active:

```bash
python backend/tools/validate_runtime.py \
  --base-url http://127.0.0.1:8000 \
  --duration 900 \
  --interval 5 \
  --output vms_runtime_validation.json \
  --fail-on-errors
```

The report records API availability/latency, observed camera streams, detection activity, and NVIDIA GPU memory/utilization/temperature when `nvidia-smi` is available. A GitHub runner cannot replace this test because it does not have the deployment cameras or RTX GPU.

### Face-recognition threshold calibration

Create labelled genuine/impostor pairs from the **same embedding backend and real camera conditions**. Each pair needs a measured distance and the correct identity relationship:

```json
[
  {"distance": 0.41, "same_identity": true},
  {"distance": 0.63, "same_identity": false}
]
```

Then calibrate instead of guessing a threshold:

```bash
python backend/training/calibrate_face_threshold.py \
  --pairs reviewed_face_pairs.json \
  --objective balanced_accuracy \
  --max-far 0.01 \
  --output face_threshold_calibration.json
```

Apply the reviewed result with `VMS_FACE_RECOGNITION_TOLERANCE`.

## 6. Promote safely

Deploy the candidate weights with:

```bash
VMS_YOLO_MODEL=/absolute/path/to/best.pt
```

Start with a shadow/canary camera group, compare alert quality, and only then roll out to all cameras.

## Runtime knobs

```bash
VMS_YOLO_DEVICE=cuda:0
VMS_YOLO_CONF=0.25
VMS_YOLO_IOU=0.55
VMS_YOLO_TRACKER=bytetrack.yaml
VMS_YOLO_SKIP_FRAMES=0

VMS_GEMMA_MODEL_PATH=/absolute/path/gemma-4-E4B-it-Q4_K_M.gguf
VMS_GEMMA_MMPROJ_PATH=/absolute/path/mmproj-gemma-4-E4B-it-BF16.gguf
VMS_GEMMA_GPU_LAYERS=-1
VMS_GEMMA_TIMEOUT_SECONDS=45

VMS_CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
```

Tune thresholds from the held-out validation set rather than by visual guesswork on one camera.
