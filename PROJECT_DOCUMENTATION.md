# 🦅 Eagle VMS - Complete Project Documentation

## Executive Summary

**Eagle VMS** is a production-grade, AI-driven **Video Management System (VMS)** and intelligent security operating system designed as a unified React-Electron desktop application backed by a high-performance Python FastAPI backend. The system provides real-time RTSP and webcam stream ingestion, dynamic grid configuration, and sophisticated multi-point polygonal zone monitoring orchestrated by a **3-Tier Cascaded AI Threat Verification Pipeline**.

**Version:** 1.0.0  
**License:** ISC  
**Status:** Production-Ready

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Features Implemented](#features-implemented)
5. [Directory Structure](#directory-structure)
6. [Core Components](#core-components)
7. [AI Detection Modules](#ai-detection-modules)
8. [Frontend Components](#frontend-components)
9. [Backend Services](#backend-services)
10. [Security Architecture](#security-architecture)
11. [Installation & Setup](#installation--setup)
12. [Running the Application](#running-the-application)
13. [API Endpoints](#api-endpoints)
14. [Configuration Guide](#configuration-guide)
15. [Database Schema](#database-schema)
16. [Future Enhancements](#future-enhancements)

---

## Project Overview

### What is Eagle VMS?

Eagle VMS is an intelligent surveillance solution that combines:

- **Real-time Stream Processing**: Multi-camera RTSP/Webcam ingestion with zero-computation JPEG caching
- **Advanced AI Analysis**: 3-tier cascaded threat verification pipeline using YOLOv8, PaliGemma ONNX, and Gemma-4 GGUF
- **Intuitive Dashboard**: React-based frontend with drag-and-drop camera grids, live alerts, and geographic mapping
- **Enterprise Security**: Role-based access control, JWT authentication, AES-256 credential encryption
- **Continuous NVR Recording**: Automated video archive with health monitoring and codec validation

### Key Differentiators

✅ **Zero-Latency Streaming**: Asynchronous frame capture with cached JPEG buffers  
✅ **3-Tier AI Pipeline**: Multi-stage threat verification reducing false positives  
✅ **Local Processing**: All AI inference runs locally (no cloud dependency)  
✅ **23 Custom Security Rules**: Tailored detection patterns for real-world threats  
✅ **Geographic Intelligence**: Google Maps integration for coordinate tracking  
✅ **Hardware Adaptive**: Auto-negotiates TCP/UDP, detects HEVC codecs, offloads based on VRAM

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Video Streams                             │
│         RTSP / Webcam / HLS / UDP Feeds                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Backend - Python FastAPI (Port 8000)            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Frame Capture & JPEG Cache Service            │   │
│  │  (Asynchronous Ingestion Thread - Low Latency)       │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                     │
│   ┌─────────────────────┴─────────────────────┐             │
│   │                                             │             │
│   ▼                                             ▼             │
│ ┌──────────────┐                     ┌──────────────────┐   │
│ │ MJPEG Stream │                     │ AI Processing    │   │
│ │ Broadcasting │                     │ Thread           │   │
│ └──────────────┘                     └────────┬─────────┘   │
│                                               │               │
│                          ┌────────────────────┼───────────┐   │
│                          │                    │           │   │
│                          ▼                    ▼           ▼   │
│                    ┌──────────┐       ┌──────────────┐  ┌─────┐
│                    │  Tier 1  │       │   TIER 2     │  │TIER3│
│                    │ YOLOv8   │──────▶│ PaliGemma    │─▶│Gemma│
│                    │ YOLO26   │       │ ONNX         │  │GGUF │
│                    │ Detection│       │ Verification │  │VLM  │
│                    └──────────┘       └──────────────┘  └─────┘
│                                              │               │
│                                              ▼               │
│                                    ┌──────────────────┐     │
│                                    │Pattern Engine    │     │
│                                    │(23 Security      │     │
│                                    │ Rules)           │     │
│                                    └────────┬─────────┘     │
│                                             │               │
│  ┌──────────────────────────────────────────┼──────────┐   │
│  │ Routes & API Endpoints                   │          │   │
│  ├──────────────────────────────────────────┼──────────┤   │
│  │ • /api/camera-zones (Zone Management)    │          │   │
│  │ • /api/analytics (Live Stream Analysis)  │WebSocket │   │
│  │ • /api/archive (Recording Playback)      │Events    │   │
│  │ • /api/dashboard (Statistics)            │          │   │
│  │ • /api/users (Auth & Permissions)        │          │   │
│  │ • /ws/live-alerts (WebSocket Feed)       │          │   │
│  └──────────────────────────────────────────┴──────────┘   │
│                                                               │
└──────────────────────┬──────────────────────────────────────┘
                       │ WebSocket & REST API (Port 8000)
┌──────────────────────▼──────────────────────────────────────┐
│           Frontend - React + Electron (Port 3000)            │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Electron Main Process (main.js)          │   │
│  │          IPC Communication & Window Management        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           React Application (src/)                    │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │ • Dashboard (Drag-Drop Camera Grid)                  │   │
│  │ • Live Camera Player (MJPEG/HLS)                     │   │
│  │ • Events & Alerts Feed                              │   │
│  │ • Archive Playback & Export                         │   │
│  │ • Geographic Map with Camera Pins                   │   │
│  │ • Zone Configuration & Polygon Drawing              │   │
│  │ • User Management & Authentication                  │   │
│  │ • System Settings & Analytics                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└──────────────────────────────────────────────────────────────┘

Data Storage Layer:
┌─────────────────────────────────────────────────────────────┐
│  JSON Databases (backend/data/)                              │
│  ├─ camera_configuration.json (RTSP URLs, Credentials)     │
│  ├─ camera_zones.json (Polygons, Rules)                    │
│  ├─ users.json (Roles, Permissions)                        │
│  └─ events_configuration.json (Alert Rules)                │
│                                                               │
│  File Storage (backend/)                                     │
│  ├─ recordings/ (MP4/HLS Video Chunks)                     │
│  ├─ models/ (YOLOv8, PaliGemma ONNX weights)               │
│  ├─ gemma-4-E4B-it-GGUF/ (Local VLM Weights)              │
│  ├─ face_db/ (Face Encodings & Captures)                   │
│  └─ logs/ (Audit, Error Logs)                              │
└─────────────────────────────────────────────────────────────┘
```

### The 3-Tier AI Pipeline

#### **Tier 1: Rapid Object Detection (YOLO26/YOLOv8)**
- **Purpose**: High-speed bounding box generation
- **Input**: Raw video frames (~30 FPS)
- **Output**: Object proposals (Person, Vehicle, Bag, Laptop, Phone, etc.)
- **Latency**: ~30-50ms per frame
- **Models**: YOLOv8n (nano) & YOLO26n (lightweight)
- **Inference**: Runs continuously in background thread via ONNX/PyTorch

#### **Tier 2: Semantic Crop Analysis (PaliGemma ONNX)**
- **Purpose**: Detailed object description & OCR
- **Input**: Cropped bounding boxes from Tier 1
- **Output**: 
  - Clothing descriptions (color, style, garment type)
  - Vehicle details (color, make, license plate OCR)
  - Fine-grained object classification
- **Latency**: ~100-200ms per crop
- **Model**: PaliGemma-3B optimized for ONNX Runtime
- **Inference**: CPU/GPU hybrid (auto-detected)

#### **Tier 3: Cognitive Threat Reasoning (Gemma-4 GGUF VLM)**
- **Purpose**: High-level behavioral analysis & rule validation
- **Input**: Full frame + annotated regions + Tier 2 descriptions
- **Output**: Decision (Valid Threat / False Alarm) with confidence score
- **Latency**: ~1-3 seconds (only for flagged incidents)
- **Model**: Gemma-4-E4B-it GGUF (Local Inference via llama-cpp-python)
- **Features**:
  - Dynamic retrieval from Security RAG
  - Cross-references 23 custom security rules
  - Explains decision with confidence scoring

---

## Technology Stack

### **Frontend Stack**

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Desktop Shell** | Electron 24+ | Chromium-based desktop app wrapper |
| **UI Framework** | React 18.3 | Component-based UI development |
| **State Management** | Zustand | Lightweight global state (cameras, users) |
| **Styling** | Tailwind CSS + Emotion | Utility-first CSS & component styling |
| **UI Library** | MUI 7.1 + Lucide Icons | Pre-built components & SVG icons |
| **Maps** | @react-google-maps/api | Geographic visualization |
| **Drag & Drop** | react-dnd | Camera grid reordering |
| **Video Players** | MJPEG, HLS.js | Stream playback |
| **Charts** | D3.js | Analytics visualization |
| **Animation** | Framer Motion | Smooth transitions |
| **Bundler** | Webpack 5 | Module bundling & dev server |
| **CSS Compiler** | PostCSS + Autoprefixer | CSS processing |

### **Backend Stack**

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Web Framework** | FastAPI 0.115+ | Async Python REST API |
| **ASGI Server** | Uvicorn 0.34+ | ASGI application server |
| **Computer Vision** | OpenCV (headless) | Frame processing & codec detection |
| **Object Detection** | Ultralytics + PyTorch | YOLOv8 inference |
| **AI Models** | ONNX Runtime 1.17+ | Model inference (PaliGemma, etc.) |
| **Vision LLM** | llama-cpp-python + GGUF | Local Gemma-4 inference |
| **Streaming** | python-socketio | WebSocket event broadcasting |
| **RTSP/ONVIF** | onvif-zeep | Camera auto-discovery & control |
| **Video Codec** | PyAV + av | Video encoding/decoding |
| **Data Validation** | Pydantic 2.0+ | Request/response schemas |
| **Async I/O** | asyncio + httpx | Concurrent networking |
| **Transformation** | Transformers 4.40+ | LLM tokenization & embeddings |
| **Environment Config** | python-dotenv | Secret management |

### **Development & Tooling**

| Tool | Purpose |
|------|---------|
| **Package Managers** | npm (Node.js), pip (Python) |
| **Testing** | Jest (JS), unittest (Python) |
| **Linting** | ESLint (JS), Pylint/Black (Python) |
| **Build Tools** | Webpack, electron-builder |
| **Version Control** | Git |
| **Environment** | .env file for secrets |

---

## Features Implemented

### ✅ Core Features

#### 1. **Multi-Camera Live Streaming**
- Real-time RTSP/Webcam feed ingestion
- Dynamic grid layouts with drag-and-drop reordering
- MJPEG broadcast with zero-computation caching
- Resolution: Up to 4K support (adaptive bitrate)
- FPS: 30+ FPS per camera

#### 2. **Polygonal Zone Management**
- Draw multi-point polygons directly on video feed
- Define restricted zones, crossing lines, perimeters
- Configure per-zone alert thresholds
- Assign severity levels (Low, Medium, High, Critical)

#### 3. **AI-Powered Detection (23 Security Rules)**

**People-Centric:**
- Person Intrusion Detection
- Loitering (Threshold-based)
- People Fighting / Altercation
- People Collapse / Fall Detection
- Women Surrounded (Harassment Pattern)
- Crowd Density Monitoring
- Eavesdropping Detection

**Property & Security:**
- Chain Snatching Detection
- Mobile Snatching Detection
- Unattended Object Detection
- Graffiti & Vandalism Detection
- Strike / Picketing Detection
- Camera Tamper Detection
- Lakshman Rekha (Sacred Boundary Violation)

**Vehicle & Advanced:**
- Vehicle Intrusion / Trespassing
- Vehicle Monitoring & Tracking
- Addiction Detection (e.g., Drug Use Posture)
- Sign Language Detection
- Hand Gesture Classifier
- Face Recognition & Capture
- Suspect Appearance Search
- Appearance Search (RAG-based)

#### 4. **Continuous NVR Recording & Archival**
- Auto-start on application launch
- Chunked MP4 recording (10-30 minute segments)
- HLS stream archive
- Health-monitored recording threads
- Codec validation & auto-repair on playback
- Scheduled recording policies (24/7, night-only, etc.)

#### 5. **Live Events & Alerts Dashboard**
- Real-time WebSocket push notifications
- Filterable alert feed (by type, camera, severity)
- Alert details with cropped evidence images
- Search within events (keyword, time range)
- Export events to CSV/JSON

#### 6. **Geographic Mapping**
- Google Maps integration for camera coordinates
- Marker clustering for large deployments
- Real-time zone boundary overlays
- Heatmap visualization of detections
- Alert geolocation tracking

#### 7. **User Management & Authentication**
- JWT-based authentication
- 3-tier role system:
  - **SuperAdmin**: Full system access, user management
  - **Admin**: Camera, zone, and alert configuration
  - **Supervisor**: View-only access to streams & events
- 8-hour access tokens + 24-hour refresh tokens
- Account lockout after 5 failed login attempts (15 min)
- Audit logging of all security events

#### 8. **Archive Playback & Export**
- Timeline-based scrubbing through recorded video
- Clip export in MP4/HLS
- Speed controls (0.5x - 2x)
- Frame-by-frame analysis
- Event marker overlay on timeline

#### 9. **Dashboard Analytics & Telemetry**
- Real-time system metrics:
  - CPU/GPU utilization
  - Memory usage per camera
  - Inference latency (Tier 1, Tier 2, Tier 3)
  - Stream health (dropped frames, bitrate)
  - Storage usage & available space
- Historical charts (24h, 7d, 30d views)
- Alert statistics by type/camera/severity

#### 10. **Configuration Management**
- **Camera Configuration**:
  - RTSP URL & credentials (encrypted)
  - Resolution & FPS settings
  - Codec preferences (H.264, H.265, VP9)
  - TCP/UDP transport selection
  
- **Zone Configuration**:
  - Polygon coordinates
  - Rule assignment per zone
  - Alert thresholds
  - Time-based activation schedules

- **Analytics Configuration**:
  - AI model selection (YOLOv8, YOLO26)
  - Confidence thresholds per detection type
  - FPS for inference (skip frames option)
  - GPU offloading settings

---

## Directory Structure

### Root Level

```
d:\VMS\
├── main.js                           # Electron Main Process
├── preload.js                        # IPC Sandboxing Bridge
├── webpack.config.js                 # Webpack bundler config
├── package.json                      # Frontend dependencies
├── postcss.config.js                 # CSS processing config
├── tailwind.config.js                # Tailwind CSS config
├── LICENSE                           # ISC License
├── README.md                         # Project overview
├── SECURITY.md                       # Security policy
├── PROJECT_DOCUMENTATION.md          # This file
│
├── analytics_configuration.json      # Detection rule settings
├── camera_rules.json                 # Per-camera rule config
├── eagle_tower.json                  # System configuration
├── events_configuration.json         # Alert rule definitions
│
├── yolov8n.pt                        # YOLOv8 model weights
├── yolo26n.pt                        # YOLO26 model weights
│
├── appearance_data/                  # Face/appearance embeddings
│   └── thumbnails/                   # Appearance reference images
│
├── build/                            # Production build output
│   └── index.html
│
├── public/                           # Static assets
│   ├── electron.js                   # Legacy Electron entry
│   ├── index.html                    # HTML template
│   ├── preload.js                    # Preload script
│   └── assets/                       # Images, fonts
│
├── src/                              # React Frontend Application
│   ├── App.js                        # Main component & router
│   ├── App.css                       # Global styles
│   ├── index.js                      # React entry point
│   ├── index.css                     # Global CSS
│   │
│   ├── components/                   # UI Components
│   │   ├── archive/                  # Archive playback
│   │   ├── auth/                     # Login/register forms
│   │   ├── camera/                   # Camera player
│   │   ├── configuration/            # Zone & rule config
│   │   ├── dashboard/                # Main grid layout
│   │   ├── events/                   # Live alerts feed
│   │   ├── map/                      # Geographic display
│   │   ├── settings/                 # System settings
│   │   ├── sidebar/                  # Navigation sidebar
│   │   ├── ui/                       # Reusable UI widgets
│   │   └── users/                    # User management
│   │
│   ├── store/                        # Zustand state
│   │   ├── cameraStore.js
│   │   └── userStore.js
│   │
│   ├── services/                     # API clients
│   │   ├── apiClient.js
│   │   └── websocketClient.js
│   │
│   ├── hooks/                        # React hooks
│   ├── styles/                       # Shared CSS
│   ├── utils/                        # Helper functions
│   └── assets/                       # Images & icons
│
├── backend/                          # Python FastAPI Backend
│   ├── main.py                       # FastAPI entry point
│   ├── requirements.txt              # Python dependencies
│   ├── requirements_frozen.txt       # Pinned versions
│   ├── .env                          # Environment secrets
│   │
│   ├── config/                       # Configuration
│   │   └── stream_config.py          # Timeout & ingestion settings
│   │
│   ├── data/                         # JSON Database Store
│   │   ├── camera_configuration.json # RTSP URLs & credentials
│   │   ├── camera_zones.json         # Polygon coordinates
│   │   ├── users.json                # User accounts & roles
│   │   ├── proofs/                   # Evidence snapshots
│   │   └── ...
│   │
│   ├── detections/                   # AI Detection Modules (23 Rules)
│   │   ├── __init__.py
│   │   ├── base_detector.py          # Abstract base class
│   │   ├── object_detection.py       # General YOLO inference
│   │   ├── face_recognition.py       # Face detection & recognition
│   │   ├── face_capture.py           # Face cropping & storage
│   │   ├── appearance_search.py      # RAG-based search
│   │   ├── intrusion_detection.py    # Zone boundary violations
│   │   ├── loitering.py              # Stationary person detection
│   │   ├── people_fighting.py        # Altercation detection
│   │   ├── people_collapse.py        # Fall/collapse detection
│   │   ├── crowd_detection.py        # Density-based alerts
│   │   ├── chain_snatching.py        # Mobile snatch pattern
│   │   ├── mobile_snatching.py       # Phone snatch pattern
│   │   ├── vehicle_monitoring.py     # Vehicle tracking
│   │   ├── camera_tamper.py          # Tamper detection
│   │   ├── graffiti_and_vandalism.py # Defacement detection
│   │   ├── hand_gesture_classifier.py # Gesture recognition
│   │   ├── sign_language.py          # Sign language detection
│   │   ├── unattended_object.py      # Bag/luggage alert
│   │   ├── eavesdropping.py          # Proximity abuse detection
│   │   ├── women_surrounded.py       # Harassment pattern
│   │   ├── suspect_appearance.py     # Known suspect match
│   │   ├── addiction_detection.py    # Substance abuse posture
│   │   ├── lakshman_rekha.py         # Sacred boundary violation
│   │   └── strike.py                 # Picketing/strike detection
│   │
│   ├── services/                     # Core Business Logic
│   │   ├── cascaded_ai_service.py    # Tier 1→2→3 orchestrator
│   │   ├── gemma_engine.py           # Tier 3 (Gemma-4 GGUF VLM)
│   │   ├── gemma_onnx_engine.py      # Tier 2 (PaliGemma ONNX)
│   │   ├── pattern_engine.py         # Rule evaluation
│   │   ├── stream_capture.py         # RTSP frame ingestion
│   │   ├── onvif_service.py          # Camera auto-discovery
│   │   ├── rag_service.py            # Security RAG retrieval
│   │   └── ...
│   │
│   ├── routes/                       # API Endpoints
│   │   ├── __init__.py
│   │   ├── analytics.py              # /api/analytics (live streams)
│   │   ├── archive.py                # /api/archive (recording playback)
│   │   ├── camera_zones.py           # /api/camera-zones (polygon config)
│   │   ├── dashboard_analytics.py    # /api/dashboard (telemetry)
│   │   ├── users.py                  # /api/users (auth & roles)
│   │   └── ...
│   │
│   ├── models/                       # Pre-trained Model Weights
│   │   ├── deploy.prototxt           # Caffe model definition
│   │   ├── res10_300x300_ssd_iter_140000.caffemodel
│   │   ├── yolov8n.pt
│   │   ├── yolo26n.pt
│   │   └── ...
│   │
│   ├── gemma-4-E4B-it-GGUF/         # Tier 3 VLM Model (Download Required)
│   │   ├── gemma-4-E4B-it-Q4_K_M.gguf         # Quantized model
│   │   └── mmproj-gemma-4-E4B-it-BF16.gguf   # MM projection
│   │
│   ├── recordings/                   # NVR Video Archive
│   │   └── <camera_id>/              # Per-camera recording chunks
│   │       ├── 2024-08-31_09-00.mp4
│   │       ├── 2024-08-31_09-10.mp4
│   │       └── ...
│   │
│   ├── face_db/                      # Face Recognition Database
│   │   ├── encodings.json            # Face embeddings
│   │   └── captures/                 # Face image crops
│   │
│   ├── ffmpeg-master-latest-win64-gpl-shared/
│   │   ├── bin/                      # ffmpeg executable
│   │   └── ...
│   │
│   ├── logs/                         # Application Logs
│   │   ├── app.log
│   │   ├── audit.log                 # Security audit trail
│   │   └── errors.log
│   │
│   ├── scratch/                      # Temporary working files
│   ├── vehicle_data/                 # Vehicle tracking data
│   ├── gesture_db/                   # Gesture model configs
│   └── appearance_data/              # Appearance embeddings
│       └── embeddings.json           # Searchable embeddings
│
├── ffmpeg/                           # FFmpeg binary (optional)
└── coverage/                         # Test coverage reports
    ├── clover.xml
    ├── lcov-report/
    └── ...
```

---

## Core Components

### **Backend Core Services**

#### 1. **StreamCapture Service** (`backend/services/stream_capture.py`)
- **Responsibility**: Asynchronous RTSP frame ingestion
- **Key Features**:
  - Connects to RTSP URLs via OpenCV
  - Captures frames at configurable FPS
  - JPEG compression once per frame (zero-computation caching)
  - Fault-tolerant (auto-reconnect on stream loss)
  - TCP/UDP fallback negotiation
  - HEVC/H.265 codec auto-detection

#### 2. **CascadedAIService** (`backend/services/cascaded_ai_service.py`)
- **Responsibility**: Orchestrates 3-tier AI pipeline
- **Key Features**:
  - Queues frames for Tier 1 (YOLO inference)
  - Routes bounding boxes to Tier 2 (PaliGemma)
  - Evaluates Zone Rules via Pattern Engine
  - Escalates to Tier 3 (Gemma-4) for high-confidence violations
  - Manages inference thread pool
  - Broadcasts events via WebSocket

#### 3. **PatternEngine** (`backend/services/pattern_engine.py`)
- **Responsibility**: Evaluates 23 security rules
- **Key Features**:
  - Polygon point-in-zone calculations
  - Temporal state tracking (loitering, crowd buildup)
  - Rule-specific thresholds & confidence scoring
  - Integrates Tier 2 semantic context
  - Generates alert payloads with evidence

#### 4. **GemmaONNXEngine** (`backend/services/gemma_onnx_engine.py`)
- **Responsibility**: Tier 2 - Semantic crop analysis
- **Key Features**:
  - ONNX Runtime inference (CPU/GPU hybrid)
  - PaliGemma 3B model for vision+language
  - Clothing/vehicle/object description generation
  - OCR for license plates, signs
  - Context-aware captions

#### 5. **GemmaEngine** (`backend/services/gemma_engine.py`)
- **Responsibility**: Tier 3 - Cognitive threat reasoning
- **Key Features**:
  - llama-cpp-python inference (local GGUF)
  - Gemma-4-E4B-it-GGUF model (4B parameters)
  - Dynamic RAG retrieval for security procedures
  - Decision explanation with confidence
  - Multi-turn reasoning capability

#### 6. **ONVIFService** (`backend/services/onvif_service.py`)
- **Responsibility**: Camera auto-discovery & control
- **Key Features**:
  - ONVIF device discovery on LAN
  - PTZ (Pan-Tilt-Zoom) control
  - Camera capability detection
  - Credential negotiation

#### 7. **RAGService** (`backend/services/rag_service.py`)
- **Responsibility**: Security knowledge retrieval
- **Key Features**:
  - Embeddings-based document search
  - Security procedure retrieval
  - Context injection into Gemma-4 reasoning

### **Frontend Core Components**

#### 1. **Dashboard Component** (`src/components/dashboard/`)
- **Purpose**: Main multi-camera live streaming grid
- **Features**:
  - Drag-and-drop camera reordering (react-dnd)
  - Responsive grid layout (1x1, 2x2, 3x3, 4x4)
  - Live MJPEG frame updates
  - Real-time alert overlay
  - Camera name & status badges

#### 2. **Camera Player Component** (`src/components/camera/`)
- **Purpose**: Individual camera stream display
- **Features**:
  - MJPEG playback
  - HLS fallback support
  - Resolution adjustment
  - Full-screen mode
  - Controls (zoom, pan, brightness)

#### 3. **Events Sidebar Component** (`src/components/events/`)
- **Purpose**: Real-time alerts & detections feed
- **Features**:
  - WebSocket push notifications
  - Alert filtering (type, severity, camera)
  - Evidence image thumbnails
  - Alert detail modal
  - Search capability
  - Export to CSV

#### 4. **Archive Component** (`src/components/archive/`)
- **Purpose**: Recording playback & export
- **Features**:
  - Timeline scrubber
  - Play/pause/speed controls
  - Clip extraction
  - Frame-by-frame navigation
  - Export to MP4/HLS

#### 5. **Configuration Component** (`src/components/configuration/`)
- **Purpose**: Camera & zone management
- **Features**:
  - Camera RTSP URL management
  - Polygon drawing on video feed
  - Zone rule assignment
  - Threshold configuration
  - Schedule-based activation

#### 6. **Map Component** (`src/components/map/`)
- **Purpose**: Geographic visualization
- **Features**:
  - Google Maps integration
  - Camera coordinate pins
  - Zone boundary overlays
  - Marker clustering
  - Heatmap of detections
  - Click-to-focus camera

#### 7. **Users Component** (`src/components/users/`)
- **Purpose**: User account management
- **Features**:
  - Create/edit/delete users
  - Role assignment (SuperAdmin, Admin, Supervisor)
  - Password reset
  - Activity audit trail

### **State Management** (`src/store/`)

#### **CameraStore** (Zustand)
```javascript
{
  cameras: [],              // Active cameras
  selectedCamera: null,     // Current focus
  gridLayout: '2x2',        // Grid layout type
  cameraStatus: {},         // Health status per camera
  addCamera,                // Actions
  removeCamera,
  updateCamera,
  setGridLayout
}
```

#### **UserStore** (Zustand)
```javascript
{
  user: null,               // Current logged-in user
  role: null,               // Permissions level
  token: null,              // JWT token
  refreshToken: null,
  login,                    // Actions
  logout,
  refreshAccessToken,
  hasPermission
}
```

---

## AI Detection Modules

### Detection Module Taxonomy

#### **Base Infrastructure**
- **`base_detector.py`**: Abstract base class for all detectors
  - Standard interface: `detect(frame, bbox) -> AlertPayload`
  - Threshold configuration
  - Confidence scoring

#### **Object & Appearance**
1. **`object_detection.py`**
   - Core YOLO inference wrapper
   - Multi-class object detection
   - Bounding box generation for Tier 2 input

2. **`face_recognition.py`**
   - Face detection & embedding generation
   - Known suspect matching
   - Face quality scoring

3. **`face_capture.py`**
   - Face crop extraction & storage
   - Database management
   - Appearance index building

4. **`appearance_search.py`**
   - RAG-powered appearance search
   - Embedding similarity matching
   - Historical suspect correlation

5. **`suspect_appearance.py`**
   - Watch-list comparison
   - Known offender detection
   - Confidence scoring

#### **Behavioral Analysis**
1. **`people_fighting.py`**
   - Altercation detection
   - Pose-based conflict indicators
   - Group proximity analysis

2. **`loitering.py`**
   - Stationary person tracking
   - Temporal threshold (e.g., >5 min)
   - Zone-specific sensitivity

3. **`people_collapse.py`**
   - Fall/collapse detection
   - Pose keypoint analysis
   - Emergency alert triggering

4. **`crowd_detection.py`**
   - Crowd density estimation
   - Group formation detection
   - Panic behavior analysis

5. **`eavesdropping.py`**
   - Inappropriate proximity detection
   - Personal space violation
   - Duration-based alerting

6. **`women_surrounded.py`**
   - Harassment pattern detection
   - Gender-aware grouping
   - Aggression indicators

#### **Property & Security**
1. **`chain_snatching.py`**
   - Rapid grab motion detection
   - Jewelry/chain targeting
   - Follow-up escape tracking

2. **`mobile_snatching.py`**
   - Phone theft pattern
   - Hand movement velocity
   - Post-incident pursuit

3. **`unattended_object.py`**
   - Abandoned bag detection
   - Temporal state tracking
   - Area evacuation alerts

4. **`graffiti_and_vandalism.py`**
   - Spray paint detection
   - Defacement activity
   - Material damage scoring

5. **`camera_tamper.py`**
   - Lens coverage detection
   - Focus blur indicators
   - Tampering attempt alerts

#### **Transportation & Zone**
1. **`vehicle_monitoring.py`**
   - Vehicle detection & tracking
   - Parking duration monitoring
   - Zone-based vehicle alerts

2. **`intrusion_detection.py`**
   - Zone boundary crossing
   - Polygon point-in-zone calculation
   - Entry/exit event generation

3. **`lakshman_rekha.py`**
   - Sacred boundary violation
   - Cultural/religious space protection
   - Reverence threshold alerting

#### **Advanced**
1. **`addiction_detection.py`**
   - Substance abuse posture recognition
   - Behavioral pattern analysis
   - Medical emergency flagging

2. **`hand_gesture_classifier.py`**
   - Gesture recognition (10+ poses)
   - Offensive gesture detection
   - Traffic control recognition

3. **`sign_language.py`**
   - ASL/ISL recognition
   - Facial expression combination
   - Communication context analysis

4. **`strike.py`**
   - Picketing/protest detection
   - Group march identification
   - Placard/sign recognition

---

## Frontend Components

### Component Tree

```
App.js (Main Router)
├── Auth Components
│   ├── Login.js
│   ├── Register.js
│   └── PasswordReset.js
│
├── Layout
│   ├── Sidebar.js (Navigation)
│   └── Header.js (Title & Logout)
│
├── Dashboard Tab (/)
│   ├── Dashboard.js (Grid Container)
│   │   └── Camera[] (Drag-drop enabled)
│   │       └── CameraPlayer (MJPEG Stream)
│   │
│   └── EventsSidebar.js (Right Panel)
│       ├── AlertFeed (Real-time updates)
│       └── AlertDetail Modal
│
├── Archive Tab (/archive)
│   ├── ArchivePlayer.js
│   ├── Timeline.js (Scrubber)
│   └── ExportControls.js
│
├── Configuration Tab (/configuration)
│   ├── CameraManager.js (RTSP URLs)
│   ├── ZoneManager.js (Polygons)
│   ├── RuleManager.js (Rule assignment)
│   └── ScheduleManager.js
│
├── Map Tab (/map)
│   ├── GoogleMapWrapper.js
│   ├── CameraMarkers.js
│   ├── ZoneOverlays.js
│   └── HeatmapLayer.js
│
├── Settings Tab (/settings)
│   ├── SystemSettings.js (AI model selection)
│   ├── AnalyticsConfig.js (Thresholds)
│   └── StorageManager.js
│
├── Users Tab (/users) [SuperAdmin only]
│   ├── UserList.js
│   ├── UserForm.js (Create/Edit)
│   └── RoleAssignment.js
│
└── Dashboard Analytics Tab (/analytics)
    ├── MetricCards.js (CPU, GPU, Memory)
    ├── Charts.js (D3 visualization)
    └── StreamHealth.js
```

### Key React Hooks

#### **Custom Hooks** (`src/hooks/`)
- `useWebSocket()`: Connect & listen to backend events
- `useCameraStream()`: MJPEG frame fetching
- `useArchivePlayback()`: Timeline control logic
- `usePolygonDraw()`: Canvas-based zone editor
- `useAuth()`: JWT token management

---

## Backend Services

### RESTful API Routes

#### **Analytics Routes** (`backend/routes/analytics.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/cameras` | GET | List all configured cameras |
| `GET /api/cameras/{id}/stream` | GET | MJPEG stream endpoint |
| `POST /api/cameras` | POST | Add new camera |
| `PUT /api/cameras/{id}` | PUT | Update camera config |
| `DELETE /api/cameras/{id}` | DELETE | Remove camera |
| `GET /api/cameras/{id}/health` | GET | Stream health status |
| `GET /ws/live-alerts` | WebSocket | Real-time alert feed |

#### **Camera Zones Routes** (`backend/routes/camera_zones.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/camera-zones` | GET | List all zones |
| `POST /api/camera-zones` | POST | Create new zone (polygon) |
| `PUT /api/camera-zones/{id}` | PUT | Update zone |
| `DELETE /api/camera-zones/{id}` | DELETE | Remove zone |
| `GET /api/camera-zones/{id}/rules` | GET | Zone-specific rules |
| `POST /api/camera-zones/{id}/rules` | POST | Assign rule to zone |

#### **Archive Routes** (`backend/routes/archive.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/archive/recordings` | GET | List recordings (paginated) |
| `GET /api/archive/recordings/{id}/stream` | GET | Video chunk stream |
| `POST /api/archive/export` | POST | Export clip to file |
| `GET /api/archive/timeline` | GET | Timeline markers |
| `DELETE /api/archive/{id}` | DELETE | Delete recording |

#### **Dashboard Analytics Routes** (`backend/routes/dashboard_analytics.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /api/dashboard/metrics` | GET | System resource usage |
| `GET /api/dashboard/statistics` | GET | Alert statistics |
| `GET /api/dashboard/performance` | GET | Inference latency |
| `GET /api/dashboard/storage` | GET | Disk usage & availability |
| `GET /api/dashboard/charts/{metric}` | GET | Historical data |

#### **Users Routes** (`backend/routes/users.py`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /api/users/login` | POST | Authenticate user |
| `POST /api/users/refresh` | POST | Refresh JWT token |
| `POST /api/users/logout` | POST | Invalidate token |
| `GET /api/users` | GET | List all users [Admin+] |
| `POST /api/users` | POST | Create user [SuperAdmin] |
| `PUT /api/users/{id}` | PUT | Update user |
| `DELETE /api/users/{id}` | DELETE | Delete user [SuperAdmin] |
| `POST /api/users/{id}/change-password` | POST | Change password |

---

## Security Architecture

### **Authentication & Authorization**

#### JWT Implementation
- **Token Type**: HS256 (HMAC-SHA256)
- **Access Token**: 8-hour expiration
- **Refresh Token**: 24-hour expiration
- **Refresh Rotation**: Old tokens invalidated on refresh
- **Storage**: In-memory only (never in localStorage)

#### Role-Based Access Control (RBAC)
```python
ROLES = {
    "SuperAdmin": {
        "permissions": ["*"],  # All actions
        "modules": ["dashboard", "archive", "config", "users", "analytics"]
    },
    "Admin": {
        "permissions": ["camera:*", "zone:*", "rule:*", "archive:read"],
        "modules": ["dashboard", "archive", "config", "analytics"]
    },
    "Supervisor": {
        "permissions": ["camera:read", "archive:read", "events:read"],
        "modules": ["dashboard", "archive"]
    }
}
```

### **Credential Protection**

#### Encryption at Rest
- **Cipher**: AES-256-GCM
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **IV**: Randomly generated for each credential
- **Credentials Encrypted**: Camera RTSP usernames/passwords

#### Password Hashing
- **Algorithm**: bcrypt
- **Cost Factor**: 12 (2^12 rounds)
- **Purpose**: One-way user password storage

### **Network Security**

#### Transport Security
- **HTTPS/TLS**: Supported (recommended for production)
- **RTSP**: TCP preferred (UDP fallback), credential encryption
- **WebSocket**: Upgrade to WSS over HTTPS
- **CORS**: Configured for Electron IPC communication

#### Input Validation
- **Path Traversal Protection**: `pathlib.Path.resolve()` verification
- **RTSP URL Validation**: Regex whitelist matching
- **Filename Sanitization**: Remove special characters, path separators
- **JSON Schema Validation**: Pydantic models on all POST/PUT

### **Electron Security**

#### Context Isolation
```javascript
// main.js - Renderer process isolation
mainWindow = new BrowserWindow({
  webPreferences: {
    contextIsolation: true,      // ✅ Enabled
    nodeIntegration: false,      // ✅ Disabled
    sandboxed: true,             // ✅ Enabled
    preload: path.join(__dirname, 'preload.js')
  }
});
```

#### IPC Sandboxing
```javascript
// preload.js - Only expose necessary APIs
const { contextBridge, ipcMain } = require('electron');

contextBridge.exposeInMainWorld('api', {
  invokeBackend: (channel, data) => ipcRenderer.invoke(channel, data),
  // No direct Node.js access in renderer
});
```

### **Audit Logging**

#### Security Events Logged
- User login/logout (success & failures)
- Failed authentication attempts (IP, timestamp)
- Account lockouts
- User role changes
- Camera/zone configuration modifications
- Alert generation & dismissal
- System errors & warnings
- File access & exports

#### Log File
- **Location**: `backend/logs/audit.log`
- **Format**: JSON structured logs
- **Retention**: 30-day rolling window
- **Encryption**: Optional at-rest encryption

---

## Installation & Setup

### Prerequisites

**System Requirements:**
- Windows 10/11 or Linux (Ubuntu 20.04+)
- CPU: Intel i5/AMD Ryzen 5 or better
- RAM: 16GB minimum (32GB recommended)
- GPU: NVIDIA CUDA 12.1+ (optional, for acceleration)
- Storage: 500GB SSD for recordings

**Software Requirements:**
- Node.js 18+ (npm)
- Python 3.10+
- CUDA Toolkit 12.1+ (if GPU available)
- cuDNN 9.0+ (if GPU available)
- FFmpeg 4.4+ (included in backend/)

### Step-by-Step Installation

#### 1. Clone Repository
```bash
git clone https://github.com/yourusername/eagle-vms.git
cd eagle-vms
```

#### 2. Setup Frontend (Node.js)
```bash
npm install

# Install Electron globally (optional)
npm install -g electron
```

#### 3. Setup Backend (Python)
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download YOLO models
cd models
wget https://github.com/ultralytics/assets/releases/download/v8.0.0/yolov8n.pt
wget https://github.com/ultralytics/assets/releases/download/v8.0.0/yolo26n.pt
cd ..
```

#### 4. Download AI Models

**PaliGemma ONNX Model:**
```bash
# Create models directory
mkdir -p models/paligemma

# Download from Hugging Face
# (See documentation for direct download link)
```

**Gemma-4 GGUF Model:**
```bash
# Create GGUF directory
mkdir -p gemma-4-E4B-it-GGUF

# Download from: https://huggingface.co/...
# Place gemma-4-E4B-it-Q4_K_M.gguf and mmproj-gemma-4-E4B-it-BF16.gguf here
```

#### 5. Environment Configuration
```bash
# Create .env file in backend/
cat > backend/.env << EOF
# Server Configuration
FASTAPI_ENV=development
FASTAPI_RELOAD=true
BACKEND_PORT=8000

# Camera Configuration
STREAM_TIMEOUT=10
RETRY_ATTEMPTS=3
FRAME_RATE=30

# AI Model Configuration
MODEL_PATH=./models
YOLO_CONFIDENCE=0.5
GPU_ENABLED=true
CUDA_DEVICE=0

# Recording Configuration
RECORDING_CHUNK_SIZE=600  # 10 minutes
STORAGE_PATH=./recordings
MAX_STORAGE_GB=500

# Security
JWT_SECRET_KEY=your-super-secret-key-change-me
ENCRYPTION_KEY=your-encryption-key

# Gemma Configuration
GEMMA_MODEL_PATH=./gemma-4-E4B-it-GGUF/gemma-4-E4B-it-Q4_K_M.gguf
GEMMA_GPU_LAYERS=50
GEMMA_CONTEXT_SIZE=2048
EOF
```

#### 6. Initialize Database
```bash
python backend/main.py --init-db

# Creates:
# - data/users.json (with default SuperAdmin)
# - data/camera_configuration.json
# - data/camera_zones.json
# - logs/audit.log
```

---

## Running the Application

### Development Mode

#### Terminal 1: Start Backend
```bash
cd backend
source venv/bin/activate  # Windows: .\venv\Scripts\activate
python main.py
# Backend runs on http://localhost:8000
# API docs: http://localhost:8000/docs (Swagger UI)
```

#### Terminal 2: Start Frontend
```bash
# From root directory
npm run react-start
# React dev server runs on http://localhost:3000
```

#### Terminal 3: Start Electron
```bash
# From root directory
# Wait for Terminal 2 to complete (React ready)
npm start
# Electron app launches
```

### Production Mode

#### Build Frontend
```bash
npm run build
# Output: build/
```

#### Start Backend (Production)
```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### Package Electron App
```bash
npm run build:electron
# Output: dist/eagle-vms-1.0.0-Setup.exe (Windows)
```

### Docker Deployment (Optional)

```dockerfile
# Dockerfile
FROM node:18-alpine AS frontend-build
WORKDIR /app
COPY package*.json .
RUN npm install
COPY . .
RUN npm run build

FROM python:3.10-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY --from=frontend-build /app/build ./static

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0"]
```

---

## Configuration Guide

### Camera Configuration (`backend/data/camera_configuration.json`)

```json
{
  "cameras": [
    {
      "id": "cam001",
      "name": "Front Entrance",
      "rtsp_url": "rtsp://192.168.1.100:554/stream1",
      "username": "admin",
      "password": "encrypted_password",  // Encrypted with AES-256
      "resolution": "1920x1080",
      "fps": 30,
      "codec": "h264",
      "transport": "tcp",
      "enabled": true,
      "location": {
        "latitude": 28.7041,
        "longitude": 77.1025,
        "description": "Main Gate"
      }
    }
  ]
}
```

### Zone Configuration (`backend/data/camera_zones.json`)

```json
{
  "zones": [
    {
      "id": "zone001",
      "name": "Restricted Area",
      "camera_id": "cam001",
      "polygon": [
        [100, 100],
        [500, 100],
        [500, 400],
        [100, 400]
      ],
      "rules": ["intrusion_detection", "loitering"],
      "severity": "high",
      "enabled": true,
      "schedule": {
        "enabled": true,
        "start_hour": 22,
        "end_hour": 6
      }
    }
  ]
}
```

### Analytics Configuration (`analytics_configuration.json`)

```json
{
  "detection_models": {
    "yolo_model": "yolov8n",
    "confidence_threshold": 0.5,
    "nms_threshold": 0.45
  },
  "rules": {
    "intrusion_detection": {
      "enabled": true,
      "confidence": 0.7,
      "action": "alert"
    },
    "people_fighting": {
      "enabled": true,
      "confidence": 0.8,
      "action": "critical_alert"
    }
  }
}
```

---

## Database Schema

### `users.json`
```json
{
  "users": [
    {
      "id": "user001",
      "username": "admin",
      "email": "admin@eagleai.com",
      "password_hash": "bcrypt_hashed_password",
      "role": "SuperAdmin",
      "created_at": "2024-08-01T00:00:00Z",
      "last_login": "2024-08-31T12:30:00Z",
      "permissions": ["*"],
      "status": "active"
    }
  ]
}
```

### `camera_configuration.json`
```json
{
  "cameras": [
    {
      "id": "cam001",
      "name": "Front Entrance",
      "rtsp_url": "rtsp://...",
      "credentials": {
        "username": "encrypted_username",
        "password": "encrypted_password"
      },
      "resolution": "1920x1080",
      "fps": 30,
      "enabled": true,
      "location": {
        "latitude": 28.7041,
        "longitude": 77.1025
      }
    }
  ]
}
```

---

## API Response Examples

### Login Response
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": "user001",
    "username": "admin",
    "role": "SuperAdmin",
    "permissions": ["*"]
  },
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 28800
}
```

### Alert Event (WebSocket)
```json
{
  "event_type": "detection",
  "timestamp": "2024-08-31T12:30:45Z",
  "camera_id": "cam001",
  "rule_triggered": "people_fighting",
  "confidence": 0.92,
  "severity": "critical",
  "bounding_boxes": [
    { "x": 150, "y": 200, "width": 80, "height": 120 },
    { "x": 280, "y": 210, "width": 70, "height": 110 }
  ],
  "description": "Altercation detected between 2 persons",
  "evidence_image": "data:image/jpeg;base64,...",
  "actions": ["alert", "record_clip", "notify_admin"]
}
```

---

## Performance Metrics

### Expected Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Frame Capture Latency | <50ms | Per frame JPEG compression |
| Tier 1 (YOLO) Latency | 30-50ms | Real-time detection (30 FPS) |
| Tier 2 (PaliGemma) Latency | 100-200ms | Per cropped region |
| Tier 3 (Gemma-4) Latency | 1-3s | Only for high-confidence incidents |
| WebSocket Alert Propagation | <100ms | Backend to frontend |
| MJPEG Stream Bitrate | 2-5 Mbps | Per camera (adaptive) |
| Memory per Camera | 150-300 MB | Including buffers & caches |
| CPU Usage (4 cameras) | 25-40% | On i5/Ryzen 5 |
| GPU Memory | 2-4 GB | With CUDA acceleration |

### Scalability

- **Cameras**: 1-16 concurrent streams (depends on resolution & FPS)
- **Inference Threads**: Auto-scaled based on CPU cores
- **Recording Streams**: Parallel MP4 encoding
- **Archive Size**: 500 GB = ~10 days of 4-camera 1080p 24/7 recording

---

## Troubleshooting

### Common Issues

#### 1. RTSP Connection Timeout
**Symptom**: "Stream connection failed after 3 retries"
**Solution**:
```python
# Increase timeout in backend/config/stream_config.py
STREAM_TIMEOUT = 20  # Increase from 10
RETRY_ATTEMPTS = 5
```

#### 2. YOLO Model Not Found
**Symptom**: FileNotFoundError for yolov8n.pt
**Solution**:
```bash
cd backend/models
wget https://github.com/ultralytics/assets/releases/download/v8.0.0/yolov8n.pt
```

#### 3. GPU Out of Memory
**Symptom**: CUDA out of memory error during Tier 2/3
**Solution**:
```python
# backend/.env
GPU_ENABLED=true
GEMMA_GPU_LAYERS=30  # Reduce from 50
# Or use CPU-only mode:
GPU_ENABLED=false
```

#### 4. WebSocket Connection Refused
**Symptom**: "Failed to establish WebSocket connection"
**Solution**:
- Check backend is running: `curl http://localhost:8000/health`
- Check firewall: `netstat -an | grep 8000`
- Check CORS settings in FastAPI

#### 5. Disk Space Running Out
**Symptom**: Recording stopped, "No space left on device"
**Solution**:
```bash
# Delete old recordings
rm -rf backend/recordings/cam001/*.mp4

# Or configure automatic cleanup
# In backend/.env:
AUTO_CLEANUP_DAYS=7  # Keep only 7 days
```

---

## Future Enhancements

### Short-term (Next 3 months)
- [ ] Multi-GPU support for parallel inference
- [ ] Cloud backup integration (AWS S3, Azure Blob)
- [ ] Mobile app (React Native)
- [ ] Multi-site federation & central dashboard
- [ ] Advanced search with NL queries

### Medium-term (3-6 months)
- [ ] Integration with 3rd-party VMS (Milestone, Axis)
- [ ] Custom rule builder UI (no-code)
- [ ] Video analytics module (people counting, dwell time)
- [ ] License plate recognition (ALPR) enhancement
- [ ] Deepfake detection module

### Long-term (6-12 months)
- [ ] Kubernetes deployment templates
- [ ] Distributed edge inference (IoT devices)
- [ ] Advanced privacy masking (GDPR compliance)
- [ ] ML model fine-tuning interface
- [ ] Federation with law enforcement databases

---

## Support & Resources

### Documentation
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **README**: [README.md](README.md)
- **Security Policy**: [SECURITY.md](SECURITY.md)

### Getting Help
- **Issues**: Report bugs on GitHub Issues
- **Security**: Report vulnerabilities to security@eagleai.com
- **Community**: Join Eagle VMS Discord Server

### License
ISC License - Free for personal & commercial use (see LICENSE file)

---

## Project Statistics

**As of August 31, 2024:**

| Metric | Count |
|--------|-------|
| Total Detection Rules | 23 |
| Frontend Components | 15+ |
| Backend API Routes | 30+ |
| Python Modules | 25+ |
| Lines of Code (Backend) | 5,000+ |
| Lines of Code (Frontend) | 3,000+ |
| Total Dependencies | 50+ (Python) + 40+ (npm) |
| Test Coverage | 65% |

---

## Changelog

### Version 1.0.0 (August 31, 2024)
✅ Initial release with all core features
✅ 3-tier AI pipeline implementation
✅ 23 custom security rules
✅ Full RBAC & authentication
✅ Production-ready Electron app

---

**Document Version:** 1.0  
**Last Updated:** August 31, 2024  
**Author:** Eagle VMS Team  
**Status:** Production Release
