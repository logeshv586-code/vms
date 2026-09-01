import json
import random
import os
from datetime import datetime, timedelta

def generate_events():
    categories = {
        "Security Analytics": ["Intrusion Detection", "Zone Monitoring", "Lakshmanrekha Crossing", "Loitering", "Camera Tamper", "Unattended Object"],
        "Crime Detection": ["Chain / Handbag Snatching", "Mobile Snatching", "People Fighting", "Eve Teasing", "Women/Infant Abduction", "Women Surrounded by Men", "Suspected Appearance"],
        "Crowd & Public Safety": ["Crowd Detection", "Person Collapsing", "Strike / Morcha / Hartal / Procession"],
        "Face Analytics": ["Face Capture", "Face Recognition", "Appearance Search"],
        "Vehicle Analytics": ["Vehicle Monitoring"],
        "Behavioral Analytics": ["Gesture Detection", "Graffiti and Vandalism Detection", "Object Classification"]
    }
    
    priorities = {
        "Critical": ["Women/Infant Abduction", "People Fighting", "Chain / Handbag Snatching", "Mobile Snatching", "Person Collapsing", "Intrusion Detection", "Women Surrounded by Men"],
        "High": ["Crowd Detection", "Camera Tamper", "Lakshmanrekha Crossing", "Zone Monitoring", "Loitering", "Eve Teasing", "Graffiti and Vandalism Detection"],
        "Medium": ["Gesture Detection", "Vehicle Monitoring", "Appearance Search", "Face Recognition", "Object Classification"],
        "Low": ["Face Capture", "Suspected Appearance", "Unattended Object", "Strike / Morcha / Hartal / Procession"]
    }
    
    cameras = ["CAM001", "CAM002", "CAM003", "CAM004", "CAM005"]
    camera_names = ["Gate 1", "Lobby", "Parking", "Main Entrance", "Corridor"]
    locations = ["Entrance", "Lobby Area", "Basement Parking", "Front Gate", "Hallway A"]
    
    events = []
    
    # Base time is now
    now = datetime.now()
    
    for i in range(1, 101):
        # Determine category and rule
        category = random.choice(list(categories.keys()))
        rule_name = random.choice(categories[category])
        
        # Determine priority based on rule_name (fallback to Medium)
        priority = "Medium"
        for p, rules in priorities.items():
            if rule_name in rules:
                priority = p
                break
                
        # Camera info
        cam_idx = random.randint(0, 4)
        
        # Status distribution
        # Active: 10%, Acknowledged: 10%, Resolved: 70%, False Positive: 10%
        status_roll = random.random()
        if status_roll < 0.15:
            status = "Active"
            acknowledged = False
        elif status_roll < 0.25:
            status = "Acknowledged"
            acknowledged = True
        elif status_roll < 0.85:
            status = "Resolved"
            acknowledged = True
        else:
            status = "False Positive"
            acknowledged = True
            
        # Times
        days_ago = random.randint(0, 7)
        minutes_ago = random.randint(1, 1440)
        created_at = now - timedelta(days=days_ago, minutes=minutes_ago)
        
        if status in ["Resolved", "False Positive"]:
            resolved_at = created_at + timedelta(seconds=random.randint(30, 3600))
            duration = (resolved_at - created_at).total_seconds()
            resolved_at_str = resolved_at.isoformat()
        else:
            resolved_at_str = None
            duration = (now - created_at).total_seconds()
            
        event = {
            "event_id": f"EVT{i:03d}",
            "rule_id": random.randint(1, 23),
            "category": category,
            "rule_name": rule_name,
            "camera_id": cameras[cam_idx],
            "camera_name": camera_names[cam_idx],
            "location": locations[cam_idx],
            "priority": priority,
            "status": status,
            "snapshot_path": "/images/mock_snapshot.jpg",
            "video_clip": "/videos/mock_event.mp4",
            "acknowledged": acknowledged,
            "created_at": created_at.isoformat(),
            "resolved_at": resolved_at_str,
            "duration": int(duration),
            "confidence": round(random.uniform(0.60, 0.99), 2)
        }
        events.append(event)
        
    return events

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    events = generate_events()
    with open("data/event_records.json", "w") as f:
        json.dump(events, f, indent=2)
    print(f"Generated {len(events)} events in data/event_records.json")
