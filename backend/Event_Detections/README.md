# Appearance Search Feature

This feature allows you to search for persons and objects in recorded videos using YOLO object detection.

## Features

- **Person Search**: Upload a reference image and find similar persons in recorded videos
- **Object Search**: Search for specific objects (cars, bags, animals, etc.) in recorded videos
- **Stream Filtering**: Search in specific camera streams or across all streams
- **Real-time Results**: Get timestamped results with confidence scores

## Requirements

The following Python packages are required:

```
ultralytics>=8.0.0
torch>=2.0.0
torchvision>=0.15.0
opencv-python-headless>=4.8.0
numpy>=1.21.0
Pillow>=8.3.0
```

## Installation

1. Install the required packages:
```bash
cd backend
pip install -r requirements.txt
```

2. Make sure the YOLO model file (`yolov8n.pt`) is present in the backend directory.

3. Ensure the recordings directory exists with video files organized by stream:
```
backend/recordings/
├── Eagle_192.168.4.242/
│   ├── video1.mp4
│   └── video2.mp4
├── Eagle_192.168.4.243/
│   └── video3.mp4
└── ...
```

## Usage

### Via Web Interface

1. Start the backend server:
```bash
cd backend
python main.py
```

2. Open the VMS web interface and navigate to:
   **Events** → **Appearance Search**

3. Choose your search type:
   - **Person Search**: Upload a reference image of the person
   - **Object Search**: Select an object from the dropdown list

4. Optionally select a specific camera stream to search in

5. Click "Start Search" to begin the search process

### Via API

#### Health Check
```bash
GET /api/appearance-search/health
```

#### Get Searchable Objects
```bash
GET /api/appearance-search/searchable-objects
```

#### Upload Reference Image
```bash
POST /api/appearance-search/upload-image
Content-Type: multipart/form-data
Body: file (image file)
```

#### Search for Object
```bash
POST /api/appearance-search/search-object
Content-Type: multipart/form-data
Body: 
  - object_name: string (required)
  - stream_id: string (optional)
```

#### Search for Person
```bash
POST /api/appearance-search/search-person
Content-Type: multipart/form-data
Body:
  - image_path: string (required, path from upload-image)
  - stream_id: string (optional)
```

## Searchable Objects

The system can detect and search for the following objects:

- **People**: person
- **Vehicles**: bicycle, car, motorcycle, airplane, bus, train, truck, boat
- **Animals**: bird, cat, dog, horse, sheep, cow, elephant, bear, zebra, giraffe
- **Objects**: backpack, umbrella, handbag, tie, suitcase, bottle, cup, chair, laptop, cell phone
- **And many more...**

## Performance Notes

- The search samples every 30th frame for faster processing
- Confidence threshold is set to 0.5 for reliable detections
- Processing time depends on the number and length of video files
- For large video archives, consider searching in specific streams

## Testing

Run the test script to verify the installation:

```bash
cd backend
python test_appearance_search.py
```

This will test:
- Search engine initialization
- YOLO model loading
- API endpoints
- Available streams detection

## Troubleshooting

### Common Issues

1. **YOLO model not found**
   - Ensure `yolov8n.pt` is in the backend directory
   - Download from: https://github.com/ultralytics/ultralytics

2. **No recordings found**
   - Check that the recordings directory exists
   - Verify video files are in the correct format (.mp4, .avi, .mkv)

3. **Import errors**
   - Install all required packages: `pip install -r requirements.txt`
   - Use a virtual environment to avoid conflicts

4. **Performance issues**
   - Reduce the number of video files for testing
   - Use specific stream filtering instead of searching all streams

### Logs

Check the backend logs for detailed error messages:
- Search progress is logged at INFO level
- Errors are logged at ERROR level
- Use `logging.DEBUG` for more detailed output

## Future Enhancements

- Face recognition using DLIB for more accurate person matching
- Caching of search results for faster repeated searches
- Background processing for large search operations
- Export search results to CSV/JSON
- Advanced filtering options (time range, confidence threshold)
