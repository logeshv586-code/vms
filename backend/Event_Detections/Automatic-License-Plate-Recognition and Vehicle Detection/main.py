from ultralytics import YOLO
import cv2
import os

import util
from sort.sort import *
from util import get_car, read_license_plate, write_csv

# Create snapshot directory if it doesn't exist
if not os.path.exists('./snapshot'):
    os.makedirs('./snapshot')

# Track unique vehicles and frame skipping
captured_vehicles = set()  # Set to store unique vehicle IDs that have been captured
frame_skip_counter = 0     # Counter to skip frames
SKIP_FRAMES = 2           # Number of frames to skip between captures

results = {}

mot_tracker = Sort()

# load models
coco_model = YOLO('yolov8n.pt')
license_plate_detector = YOLO('license_plate_detector.pt')

# load video
cap = cv2.VideoCapture('./sample.mp4')

vehicles = [2, 3, 5, 7]

# read frames
frame_nmr = -1
ret = True
while ret:
    frame_nmr += 1
    ret, frame = cap.read()
    if ret:
        results[frame_nmr] = {}
        # detect vehicles
        detections = coco_model(frame)[0]
        detections_ = []
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])

        # track vehicles
        track_ids = mot_tracker.update(np.asarray(detections_))

        # detect license plates
        license_plates = license_plate_detector(frame)[0]
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate

            # assign license plate to car
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)

            if car_id != -1:

                # crop license plate
                license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]

                # process license plate
                license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                _, license_plate_crop_thresh = cv2.threshold(license_plate_crop_gray, 64, 255, cv2.THRESH_BINARY_INV)

                # read license plate number
                license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_thresh)

                if license_plate_text is not None:
                    # Check if this vehicle is unique and if we should capture (frame skipping)
                    vehicle_key = f"{int(car_id)}_{license_plate_text}"

                    # Only capture if vehicle is unique and we're not skipping frames
                    if vehicle_key not in captured_vehicles and frame_skip_counter == 0:
                        # Save vehicle image
                        vehicle_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2), :]
                        vehicle_filename = f'./snapshot/vehicle_frame{frame_nmr}_car{int(car_id)}.jpg'
                        cv2.imwrite(vehicle_filename, vehicle_crop)

                        # Save license plate image
                        license_plate_filename = f'./snapshot/license_plate_frame{frame_nmr}_car{int(car_id)}.jpg'
                        cv2.imwrite(license_plate_filename, license_plate_crop)

                        # Save processed license plate image (thresholded)
                        license_plate_thresh_filename = f'./snapshot/license_plate_thresh_frame{frame_nmr}_car{int(car_id)}.jpg'
                        cv2.imwrite(license_plate_thresh_filename, license_plate_crop_thresh)

                        # Mark this vehicle as captured
                        captured_vehicles.add(vehicle_key)

                        print(f"Saved snapshots for UNIQUE vehicle - frame {frame_nmr}, car {int(car_id)}: {license_plate_text}")
                    elif vehicle_key in captured_vehicles:
                        print(f"Skipped duplicate vehicle - frame {frame_nmr}, car {int(car_id)}: {license_plate_text}")
                    else:
                        print(f"Skipped frame {frame_nmr} due to frame skipping (counter: {frame_skip_counter})")

                    results[frame_nmr][car_id] = {'car': {'bbox': [xcar1, ycar1, xcar2, ycar2]},
                                                  'license_plate': {'bbox': [x1, y1, x2, y2],
                                                                    'text': license_plate_text,
                                                                    'bbox_score': score,
                                                                    'text_score': license_plate_text_score}}

    # Update frame skip counter at the end of each frame
    frame_skip_counter = (frame_skip_counter + 1) % (SKIP_FRAMES + 1)

# Print summary statistics
print(f"\n=== SNAPSHOT SUMMARY ===")
print(f"Total unique vehicles captured: {len(captured_vehicles)}")
print(f"Unique vehicles: {list(captured_vehicles)}")
print(f"Frame skip setting: Skip {SKIP_FRAMES} frames between captures")

# write results
write_csv(results, './test.csv')