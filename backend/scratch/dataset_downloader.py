import os
import sys
import json
import shutil
import zipfile
import cv2

# Determine paths
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BACKEND_DIR, "data", "graffiti_vandalism")
KAGGLE_DATASET = "mostafamohamed67/vandalism-detection-dataset"

# Directory structure folders
CATEGORIES = ["graffiti", "vandalism", "normal"]
SPLITS = ["train", "val", "test"]

def create_directory_structure():
    print("=== Creating Dataset Directory Structure ===")
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for split in SPLITS:
        for category in CATEGORIES:
            path = os.path.join(DATA_DIR, split, category)
            os.makedirs(path, exist_ok=True)
            print(f"Created folder: {os.path.relpath(path, BACKEND_DIR)}")
            
            # Create a README dummy file in each folder
            with open(os.path.join(path, ".gitkeep"), "w") as f:
                f.write("")
    print("[SUCCESS] Folder structure created successfully.\n")

def check_kaggle_credentials():
    # 1. Check Env variables
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
        
    # 2. Check ~/.kaggle/kaggle.json
    home_dir = os.path.expanduser("~")
    kaggle_json_path = os.path.join(home_dir, ".kaggle", "kaggle.json")
    if os.path.exists(kaggle_json_path):
        try:
            with open(kaggle_json_path, "r") as f:
                creds = json.load(f)
                if creds.get("username") and creds.get("key"):
                    return True
        except Exception:
            pass
            
    # 3. Check current directory or backend/data directory for credentials
    local_kaggle_json = os.path.join(BACKEND_DIR, "kaggle.json")
    if os.path.exists(local_kaggle_json):
        try:
            with open(local_kaggle_json, "r") as f:
                creds = json.load(f)
                if creds.get("username") and creds.get("key"):
                    # Copy to ~/.kaggle/
                    target_dir = os.path.join(home_dir, ".kaggle")
                    os.makedirs(target_dir, exist_ok=True)
                    shutil.copy(local_kaggle_json, os.path.join(target_dir, "kaggle.json"))
                    print(f"Copied kaggle.json from local workspace to {target_dir}")
                    return True
        except Exception:
            pass
            
    return False

def download_from_kaggle():
    print(f"=== Downloading Dataset: {KAGGLE_DATASET} ===")
    
    if not check_kaggle_credentials():
        print("[WARNING] Kaggle credentials not found!")
        print("Please follow these steps to download the dataset offline:")
        print("  1. Sign in/up to Kaggle (https://www.kaggle.com).")
        print("  2. Go to your Account page, click 'Create New API Token' to download kaggle.json.")
        print("  3. Place the downloaded 'kaggle.json' file into one of these directories:")
        print(f"     - {os.path.expanduser('~')}/.kaggle/kaggle.json")
        print(f"     - {os.path.abspath(os.path.join(BACKEND_DIR, 'kaggle.json'))}")
        print("  4. Re-run this script.")
        print("\nCreating mock data files in categories for pipeline verification...")
        
        # Populate with mock files
        create_mock_files()
        return False
        
    try:
        # Dynamically install kaggle package if not present
        try:
            import kaggle
        except ImportError:
            print("Installing kaggle pip package...")
            import subprocess
            subprocess.run([sys.executable, "-m", "pip", "install", "kaggle"], check=True)
            import kaggle
            
        # Download dataset zip file
        print(f"Downloading {KAGGLE_DATASET} to {DATA_DIR}...")
        kaggle.api.dataset_download_files(KAGGLE_DATASET, path=DATA_DIR, unzip=False)
        
        # Unzip dataset
        zip_path = os.path.join(DATA_DIR, f"{KAGGLE_DATASET.split('/')[-1]}.zip")
        if os.path.exists(zip_path):
            print(f"Extracting {zip_path}...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Extract into a temp folder
                temp_extract = os.path.join(DATA_DIR, "temp_extract")
                os.makedirs(temp_extract, exist_ok=True)
                zip_ref.extractall(temp_extract)
                
                # Sort/Organise downloaded files into categories
                organise_dataset(temp_extract)
                
                # Cleanup temp folder and zip file
                shutil.rmtree(temp_extract)
            os.remove(zip_path)
            print("[SUCCESS] Dataset downloaded and organized successfully!")
            return True
        else:
            print("[ERROR] Download zip file not found after Kaggle download.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error downloading from Kaggle: {e}")
        print("Creating mock data files in categories for pipeline verification...")
        create_mock_files()
        return False

def organise_dataset(temp_path):
    """
    Simulated or actual file sorting from temp extract to final train/val/test splits.
    Since Kaggle datasets have different internal layouts, this utility acts as the layout mapper.
    """
    print("Organising files into splits and categories...")
    # Walk the temp directory and find images
    image_extensions = (".jpg", ".jpeg", ".png", ".bmp")
    all_images = []
    
    for root, _, files in os.walk(temp_path):
        for f in files:
            if f.lower().endswith(image_extensions):
                all_images.append(os.path.join(root, f))
                
    if not all_images:
        print("No source images found in dataset. Creating mock files.")
        create_mock_files()
        return

    # Sort images based on keywords or distribute uniformly for classification training
    import random
    random.shuffle(all_images)
    
    # 70% train, 20% val, 10% test
    n = len(all_images)
    train_end = int(n * 0.7)
    val_end = train_end + int(n * 0.2)
    
    for idx, img_path in enumerate(all_images):
        filename = os.path.basename(img_path)
        
        # Categorize
        if "graffiti" in filename.lower() or "spray" in filename.lower():
            cat = "graffiti"
        elif "vandal" in filename.lower() or "damage" in filename.lower():
            cat = "vandalism"
        else:
            # Fallback random category assignment if no keywords match
            cat = random.choice(CATEGORIES)
            
        # Split
        if idx < train_end:
            split = "train"
        elif idx < val_end:
            split = "val"
        else:
            split = "test"
            
        dest = os.path.join(DATA_DIR, split, cat, filename)
        shutil.copy(img_path, dest)

def create_mock_files():
    """Generates mock images/txt metadata to allow local training script verification."""
    import numpy as np
    
    for split in SPLITS:
        for cat in CATEGORIES:
            folder = os.path.join(DATA_DIR, split, cat)
            for i in range(3): # Create 3 mock images per category
                mock_name = f"mock_{split}_{cat}_{i+1}.jpg"
                mock_path = os.path.join(folder, mock_name)
                # Create a simple colored solid image
                color = (0, 0, 255) if cat == "graffiti" else ((0, 255, 0) if cat == "normal" else (255, 0, 0))
                img = np.ones((128, 128, 3), dtype=np.uint8) * np.array(color, dtype=np.uint8)
                cv2.imwrite(mock_path, img)
    print("[SUCCESS] Created mock images in train/val/test for pipeline testing.")

if __name__ == "__main__":
    create_directory_structure()
    download_from_kaggle()
