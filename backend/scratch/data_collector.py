import os
import json
import logging

logger = logging.getLogger(__name__)

# DATA SOURCE MAPPING FOR 23 RULES
DATA_SOURCES = {
    1: {"name": "Appearance Search", "source": "Market-1501, DukeMTMC-reID", "task": "Re-Identification"},
    2: {"name": "Camera Tamper", "source": "Custom dataset / Synthetic blur & occlusion", "task": "Anomaly Detection"},
    3: {"name": "Chain/Handbag Snatching", "source": "UCF-Crime (Snatching category)", "task": "Action Recognition"},
    4: {"name": "Crowd Detection", "source": "ShanghaiTech, NWPU-Crowd", "task": "Crowd Counting"},
    5: {"name": "Eve Teasing / Harassment", "source": "Social Interaction Datasets / Custom", "task": "Behavioral Analysis"},
    6: {"name": "Face Capture", "source": "WIDER FACE, LFW", "task": "Face Detection"},
    7: {"name": "Face Recognition", "source": "VGGFace2, CelebA", "task": "Face ID"},
    8: {"name": "Gesture Detection", "source": "20BN-JESTER, EgoGesture", "task": "Hand Gesture Recognition"},
    9: {"name": "Graffiti and Vandalism", "source": "Vandalism Detection Dataset (Kaggle)", "task": "Object Detection"},
    10: {"name": "Intrusion Detection", "source": "PETS2009, VIRAT", "task": "Zone Intrusion"},
    11: {"name": "Lakshmanrekha Crossing", "source": "AIC21 (Boundary crossing)", "task": "Line Crossing"},
    12: {"name": "Loitering", "source": "CAVIAR, PETS", "task": "Tracking & Persistence"},
    13: {"name": "Mobile Snatching", "source": "CCTV-Snatch (Kaggle)", "task": "Action Recognition"},
    14: {"name": "Object Classification", "source": "COCO, ImageNet-21K", "task": "Classification"},
    15: {"name": "People Fighting", "source": "RWF-2000, Hockey Fight Dataset", "task": "Fight Detection"},
    16: {"name": "Person Collapsing", "source": "Fall Detection Dataset (Kaggle / UR Fall)", "task": "Human Fall Detection"},
    17: {"name": "Strike / Morcha / Procession", "source": "News Video Datasets / Protest Datasets", "task": "Event Detection"},
    18: {"name": "Suspected Appearance", "source": "PETA (Pedestrian Attribute Dataset)", "task": "Attribute Recognition"},
    19: {"name": "Unattended Object", "source": "ABODA (Abandoned Object Dataset)", "task": "Stationary Object Detection"},
    20: {"name": "Women Surrounded", "source": "Social Dynamics / Group Behavior Datasets", "task": "Social Geometry"},
    21: {"name": "Abduction Detection", "source": "Synthetic / Kidnapping scenario datasets", "task": "Aggressive Behavior"},
    22: {"name": "Vehicle Monitoring", "source": "UA-DETRAC, VeRi", "task": "Vehicle Tracking"},
    23: {"name": "Zone Monitoring", "source": "MOT17, MOT20", "task": "Multi-Object Tracking"}
}

def collect_metadata():
    """Generates a summary of data sources for the 23 rules"""
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/sources"))
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        
    metadata_file = os.path.join(data_dir, "rule_data_sources.json")
    with open(metadata_file, "w") as f:
        json.dump(DATA_SOURCES, f, indent=4)
    
    print(f"✅ Data source metadata generated at {metadata_file}")
    print("Next step: Use Kaggle API or HuggingFace Hub to fetch pre-trained weights for these tasks.")

if __name__ == "__main__":
    collect_metadata()
