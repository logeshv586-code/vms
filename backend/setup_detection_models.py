#!/usr/bin/env python3
"""
Detection Models Setup Script
===============================
Downloads pre-trained model weights and seeds recognition databases from
Kaggle datasets (Option A — gallery reference, no model training required).

Usage:
    # From VMS/backend directory:
    python setup_detection_models.py [--kaggle-user YOUR_USER --kaggle-key YOUR_KEY]

What this script does:
  1. Downloads OpenCV DNN face detector model (Caffe) for face capture
  2. Seeds the face recognition database from a Kaggle LFW-format dataset
  3. Seeds the appearance search gallery from Market-1501 style images
  4. Sets up directory structure for all three detection systems
  5. Validates that MediaPipe (hand gesture) is installed and working

Kaggle datasets used (Option A — reference gallery seeding):
  - LFW: https://www.kaggle.com/datasets/jessicali9530/lfw-dataset
  - Market-1501: https://www.kaggle.com/datasets/pengcw1/market-1501
  - ASL Alphabet: https://www.kaggle.com/datasets/grassknoted/asl-alphabet
"""

import argparse
import json
import logging
import os
import sys
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
FACE_DB_DIR = os.path.join(BASE_DIR, "face_db")
GALLERY_DIR = os.path.join(FACE_DB_DIR, "captures")
ENCODINGS_PATH = os.path.join(FACE_DB_DIR, "encodings.json")
APPEARANCE_DIR = os.path.join(BASE_DIR, "appearance_data", "gallery")
EMBEDDINGS_PATH = os.path.join(BASE_DIR, "appearance_data", "embeddings.json")
GESTURE_DB_DIR = os.path.join(BASE_DIR, "gesture_db")


# ── OpenCV DNN Face Detector (Caffe) ─────────────────────────────────────────
DNN_PROTO_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
)
DNN_MODEL_URL = (
    "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/"
    "res10_300x300_ssd_iter_140000.caffemodel"
)


def download_face_detector_models():
    """Download OpenCV DNN face detection model files."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    proto_path = os.path.join(MODELS_DIR, "deploy.prototxt")
    model_path = os.path.join(MODELS_DIR, "res10_300x300_ssd_iter_140000.caffemodel")

    if not os.path.isfile(proto_path):
        logger.info("Downloading deploy.prototxt ...")
        try:
            urllib.request.urlretrieve(DNN_PROTO_URL, proto_path)
            logger.info("  ✓ deploy.prototxt saved to %s", proto_path)
        except Exception as e:
            logger.error("  ✗ Failed to download prototxt: %s", e)
            logger.info("  → Haar cascade fallback will be used instead.")
    else:
        logger.info("  ✓ deploy.prototxt already exists.")

    if not os.path.isfile(model_path):
        logger.info("Downloading caffemodel (5 MB) ...")
        try:
            urllib.request.urlretrieve(DNN_MODEL_URL, model_path)
            logger.info("  ✓ caffemodel saved to %s", model_path)
        except Exception as e:
            logger.error("  ✗ Failed to download caffemodel: %s", e)
    else:
        logger.info("  ✓ caffemodel already exists.")

    return os.path.isfile(proto_path) and os.path.isfile(model_path)


# ── Directory structure ───────────────────────────────────────────────────────
def setup_directories():
    """Create all required directories."""
    dirs = [
        MODELS_DIR,
        FACE_DB_DIR,
        GALLERY_DIR,
        os.path.join(FACE_DB_DIR, "watchlist_images"),
        APPEARANCE_DIR,
        os.path.join(BASE_DIR, "appearance_data", "thumbnails"),
        GESTURE_DB_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        logger.info("  ✓ Directory ready: %s", d)

    # Initialise empty JSON databases if missing
    for db_path, initial in [
        (ENCODINGS_PATH, {"encodings": {}, "categories": {}}),
        (EMBEDDINGS_PATH, {"embeddings": {}, "images": {}}),
        (os.path.join(GESTURE_DB_DIR, "gesture_config.json"), {
            "sos_wave_threshold": 3,
            "sos_wave_window": 15,
            "min_detection_confidence": 0.7,
            "alert_categories": ["help", "threat"],
        }),
    ]:
        if not os.path.isfile(db_path):
            with open(db_path, "w") as fh:
                json.dump(initial, fh, indent=2)
            logger.info("  ✓ Initialised database: %s", db_path)
        else:
            logger.info("  ✓ Database already exists: %s", db_path)


# ── Kaggle dataset seeding ────────────────────────────────────────────────────
def seed_face_recognition_from_kaggle(lfw_dir: str):
    """
    Seed the face recognition database from a downloaded LFW dataset.

    LFW format:
      lfw_dir/
        Person_Name/
          Person_Name_0001.jpg
          ...

    Each person's first image is registered as a reference encoding.
    """
    if not os.path.isdir(lfw_dir):
        logger.warning("LFW directory not found: %s. Skipping face recognition seeding.", lfw_dir)
        return

    logger.info("Seeding face recognition from: %s", lfw_dir)

    try:
        sys.path.insert(0, BASE_DIR)
        from detections.face_recognition import FaceRecognitionDetector
        detector = FaceRecognitionDetector({
            "encodings_db_path": ENCODINGS_PATH,
            "recognition_tolerance": 0.5,
        })
        result = detector.seed_from_directory(lfw_dir, category="person")
        logger.info(
            "  ✓ Face recognition seeded: %d identities registered (%d failed).",
            result.get("registered", 0),
            result.get("failed", 0),
        )
    except Exception as e:
        logger.error("  ✗ Face recognition seeding failed: %s", e)


def seed_appearance_search_from_kaggle(market1501_dir: str, max_per_person: int = 3):
    """
    Seed the appearance search gallery from a Market-1501 dataset.

    Market-1501 format:
      market1501_dir/
        bounding_box_train/ or query/
          0001_c1s1_000151_01.jpg   (person_id_cam_seq_frame_det.jpg)
          ...

    Person ID is derived from the filename prefix.
    """
    if not os.path.isdir(market1501_dir):
        logger.warning("Market-1501 directory not found: %s. Skipping.", market1501_dir)
        return

    logger.info("Seeding appearance search from: %s", market1501_dir)

    try:
        import cv2
        from detections.appearance_search import AppearanceSearchDetector
        detector = AppearanceSearchDetector({
            "gallery_path": APPEARANCE_DIR,
            "embeddings_db_path": EMBEDDINGS_PATH,
            "reid_model": "histogram",  # Use histogram (safe, no GPU needed)
        })

        # Scan for image files
        registered = 0
        person_counts: dict = {}

        for root, _, files in os.walk(market1501_dir):
            for fname in sorted(files):
                if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                # Extract person ID from filename prefix (first 4 chars)
                person_id = fname[:4] if len(fname) >= 4 else fname
                if person_counts.get(person_id, 0) >= max_per_person:
                    continue

                img_path = os.path.join(root, fname)
                img = cv2.imread(img_path)
                if img is None:
                    continue

                result = detector.register_person(
                    name=f"Person_{person_id}",
                    frame=img,
                    image_path=os.path.join(APPEARANCE_DIR, fname),
                )
                if result.get("success"):
                    person_counts[person_id] = person_counts.get(person_id, 0) + 1
                    registered += 1

                if registered >= 500:  # Cap at 500 gallery entries
                    break
            else:
                continue
            break

        logger.info("  ✓ Appearance gallery seeded: %d entries registered.", registered)
    except Exception as e:
        logger.error("  ✗ Appearance search seeding failed: %s", e)


def seed_asl_reference(asl_dir: str):
    """
    Store ASL reference images for documentation (Option A — no training).
    Creates a manifest of ASL letter reference images.

    ASL Alphabet Kaggle format:
      asl_dir/
        asl_alphabet_train/
          A/  B/  C/ ... Z/  space/  del/  nothing/
            img.jpg
    """
    if not os.path.isdir(asl_dir):
        logger.warning("ASL directory not found: %s. Skipping.", asl_dir)
        return

    logger.info("Building ASL reference manifest from: %s", asl_dir)

    manifest = {}
    asl_ref_dir = os.path.join(BASE_DIR, "gesture_db", "asl_reference")
    os.makedirs(asl_ref_dir, exist_ok=True)

    for letter_dir in sorted(os.scandir(asl_dir), key=lambda e: e.name):
        if not letter_dir.is_dir():
            continue
        letter = letter_dir.name.upper()
        if letter not in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["SPACE", "DEL", "NOTHING"]:
            continue

        # Copy first reference image
        for img_file in os.scandir(letter_dir.path):
            if img_file.name.lower().endswith((".jpg", ".jpeg", ".png")):
                import shutil
                dst = os.path.join(asl_ref_dir, f"{letter}_ref.jpg")
                shutil.copy2(img_file.path, dst)
                manifest[letter] = dst
                break

    manifest_path = os.path.join(BASE_DIR, "gesture_db", "asl_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(manifest, fh, indent=2)
    logger.info(
        "  ✓ ASL reference manifest saved: %d letters → %s",
        len(manifest),
        manifest_path,
    )


# ── Dependency validation ─────────────────────────────────────────────────────
def validate_dependencies():
    """Check that all required Python packages are installed."""
    checks = [
        ("cv2", "opencv-python"),
        ("numpy", "numpy"),
        ("ultralytics", "ultralytics (YOLOv8)"),
    ]
    optional = [
        ("mediapipe", "mediapipe (hand gesture detection — RECOMMENDED)"),
        ("face_recognition", "face_recognition (dlib — enhanced face matching)"),
        ("torchreid", "torchreid (OSNet Re-ID — enhanced appearance search)"),
    ]

    logger.info("\nRequired packages:")
    all_ok = True
    for module, name in checks:
        try:
            __import__(module)
            logger.info("  ✓ %s", name)
        except ImportError:
            logger.error("  ✗ MISSING: %s  →  pip install %s", name, module)
            all_ok = False

    logger.info("\nOptional packages (enhanced features):")
    for module, name in optional:
        try:
            __import__(module)
            logger.info("  ✓ %s", name)
        except ImportError:
            logger.warning("  ○ Not installed: %s  →  pip install %s", name, module)

    return all_ok


# ── SQLite DB initialisation ─────────────────────────────────────────────────
def initialise_face_db():
    """Ensure the SQLite database is initialised with all tables."""
    try:
        sys.path.insert(0, BASE_DIR)
        from services.face_db_service import FaceDBService
        db = FaceDBService()
        logger.info("  ✓ Face SQLite database initialised: %s", db.db_path)
        return True
    except Exception as e:
        logger.error("  ✗ Face DB initialisation failed: %s", e)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="VMS Detection Models Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic setup (no Kaggle datasets):
  python setup_detection_models.py

  # With Kaggle LFW dataset for face recognition:
  python setup_detection_models.py --lfw-dir /path/to/lfw

  # With all Kaggle datasets:
  python setup_detection_models.py \\
      --lfw-dir /path/to/lfw \\
      --market1501-dir /path/to/Market-1501 \\
      --asl-dir /path/to/asl_alphabet_train
        """,
    )
    parser.add_argument("--lfw-dir", help="Path to downloaded LFW dataset directory")
    parser.add_argument("--market1501-dir", help="Path to downloaded Market-1501 dataset")
    parser.add_argument("--asl-dir", help="Path to downloaded ASL Alphabet dataset")
    parser.add_argument(
        "--max-per-person",
        type=int,
        default=3,
        help="Max images per person to seed into appearance gallery (default: 3)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("VMS Detection Models Setup")
    logger.info("=" * 60)

    # Step 1: Validate dependencies
    logger.info("\n[1/5] Validating Python dependencies ...")
    validate_dependencies()

    # Step 2: Create directories
    logger.info("\n[2/5] Creating directory structure ...")
    setup_directories()

    # Step 3: Download DNN face detector
    logger.info("\n[3/5] Downloading OpenCV DNN face detector models ...")
    download_face_detector_models()

    # Step 4: Initialise SQLite database
    logger.info("\n[4/5] Initialising face capture SQLite database ...")
    initialise_face_db()

    # Step 5: Kaggle dataset seeding (Option A)
    logger.info("\n[5/5] Kaggle dataset seeding (Option A — gallery reference) ...")
    if args.lfw_dir:
        seed_face_recognition_from_kaggle(args.lfw_dir)
    else:
        logger.info(
            "  → Skipped LFW seeding (pass --lfw-dir to seed face recognition).\n"
            "     Download from: https://www.kaggle.com/datasets/jessicali9530/lfw-dataset"
        )

    if args.market1501_dir:
        seed_appearance_search_from_kaggle(args.market1501_dir, args.max_per_person)
    else:
        logger.info(
            "  → Skipped Market-1501 seeding (pass --market1501-dir for appearance search).\n"
            "     Download from: https://www.kaggle.com/datasets/pengcw1/market-1501"
        )

    if args.asl_dir:
        seed_asl_reference(args.asl_dir)
    else:
        logger.info(
            "  → Skipped ASL reference seeding (pass --asl-dir for ASL letter references).\n"
            "     Download from: https://www.kaggle.com/datasets/grassknoted/asl-alphabet"
        )

    logger.info("\n" + "=" * 60)
    logger.info("Setup complete!")
    logger.info(
        "Start the backend:  python backend/main.py\n"
        "Register faces via: POST /api/face/register\n"
        "View captures at:   GET  /api/face/captures\n"
        "View gestures at:   GET  /api/gestures/log"
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
