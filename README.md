# 🦅 Eagle VMS: Intelligent Video Management System & AI Security OS

Eagle VMS is a production-grade, state-of-the-art **Video Management System (VMS)** and **AI-Driven Security Operating System** designed as a unified React-Electron desktop application backed by a high-performance Python FastAPI service. 

It provides real-time RTSP and webcam stream ingestion, dynamic grid configuration, and custom multi-point polygonal zone monitoring, orchestrated by a robust **3-Tier Cascaded AI Threat Verification Pipeline** (YOLOv8/26 → ONNX PaliGemma → Local Gemma-4 GGUF VLM & Security RAG).

---

## 🏗️ System Architecture & Layered Security Model

Eagle VMS implements a high-performance, asynchronous streaming architecture coupled with a cognitive security engine that operates across three distinct computational tiers to deliver real-time, high-accuracy threat verification:

```mermaid
flowchart TD
    A[RTSP / Webcam Feeds] -->|Asynchronous Ingestion| B[Capture Thread]
    B -->|Zero-Computation JPEG Cache| C[MJPEG Broadcast & NVR Archive]
    B -->|Frame Ready Notification| D[AI processing Thread]
    
    subgraph 3-Tier AI Threat Pipeline
        D -->|Tier 1: High-Speed | E[YOLOv8 / YOLO26 Engine]
        E -->|Person/Vehicle BBoxes| F[Tier 2: Semantic Verification]
        F -->|PaliGemma ONNX crops| G[Target Descriptions & OCR]
        G -->|Rule Violations e.g., Rule 23| H[Tier 3: Deep Cognitive Reasoning]
        H -->|Gemma-4-E4B-it VLM + Security RAG| I[Decision: Validated Event / Alert]
    end
    
    I -->|WebSocket/API Trigger| J[Frontend Real-Time Alerts]
```

### 🧠 The Three AI Tiers

1. **Tier 1: Rapid Detection & Bounding Box Proposals (YOLO26 Engine)**
   * Utilizes an optimized YOLO model running in a background inference thread via ONNX or PyTorch.
   * Performs continuous object detection and multi-object tracking (Person, Vehicle, Bag, Laptop, etc.) at high frame rates to generate raw region proposals without impacting ingestion latency.

2. **Tier 2: Spatial Rules & Semantic Crop Verification (PaliGemma ONNX)**
   * Bounding box proposals are evaluated against spatial rules (restricted zone entry, boundary crossings) managed by the **Pattern Engine**.
   * Selected target region crops are routed to a local **PaliGemma ONNX model** (optimized for CPU/GPU inference via ONNX Runtime).
   * Generates micro-level semantic details such as detailed clothing description, vehicle color/type, and OCR license plate reads.

3. **Tier 3: Cognitive Threat Reasoning & Security RAG (Gemma-4 GGUF)**
   * When critical anomalies or rule violations are flagged, the frame and its localized contexts are evaluated by a local vision model **Gemma-4-E4B-it GGUF** running on `llama-cpp-python`.
   * The model dynamically retrieves relevant security procedures from the **Security RAG Service** to cross-verify the incident.
   * Performs high-level behavioral analysis across 23 custom security rules (e.g. trespassing, harassment, people fighting, snatching, unattended baggage) to validate the event and rule out false alarms before firing alerts.

---

## ✨ Feature Highlights

* **📺 Asynchronous Live Streaming Grid:** Multi-camera dashboard supporting dynamic grid layouts, interactive drag-and-drop customization (`react-dnd`), and immediate MJPEG streaming.
* **⚡ Zero-Computation JPEG Caching:** The backend ingests the RTSP feed, compresses the frame to JPEG once in memory, and caches the buffer. Multiple client grids or AI services retrieve the cached byte array, eliminating redundant compression CPU overhead.
* **🛡️ Polygonal Zone Management:** Configure multi-point polygons directly on the stream using coordinates overlay on the frontend. Define monitoring thresholds and associate rule severities (e.g., restricted zone breaching).
* **📼 Continuous NVR & Recording Archive:** Automated, health-monitored continuous and scheduled recordings saved directly in chunks (MP4/HLS). Built-in video validators automatically scan for file corruption and repair incorrect codec headers.
* **🛰️ Geographic Mapping:** Complete Google Maps integration to map camera coordinates, track collections geographically, and display zone alarms visually.
* **⚙️ Hardware Acceleration & Resilience:** Auto-negotiates RTSP over TCP with deep-probing and drops to UDP socket fallbacks when timeouts occur. Detects HEVC/H.265 video codecs and automatically configures CPU/GPU thread decoders. Automatically offloads VLM layers based on detected VRAM capacity.

---

## 📂 Repository Directory Structure

```text
VMS/
├── backend/                       # FastAPI Backend Application
│   ├── config/                    # Ingestion & Timeout Configurations
│   │   └── stream_config.py
│   ├── data/                      # JSON Databases (Users, Zones, Cameras)
│   │   ├── camera_configuration.json
│   │   ├── camera_zones.json
│   │   └── users.json
│   ├── gemma-4-E4B-it-GGUF/       # Tier 3 Vision LLM (Place GGUF models here)
│   ├── models/                    # YOLO & PaliGemma ONNX weights
│   ├── recordings/                # NVR continuous & on-demand video chunks
│   ├── routes/                    # RESTful Endpoints & Websockets
│   │   ├── analytics.py           # Live stream feeds & analysis
│   │   ├── archive.py             # Recording playbacks & exports
│   │   ├── camera_zones.py        # Polygon coordination settings
│   │   ├── dashboard_analytics.py # Statistics & telemetry logs
│   │   └── users.py               # Auth, roles, permissions
│   ├── services/                  # Core Cognitive Engines
│   │   ├── cascaded_ai_service.py # Cascaded AI pipeline orchestrator
│   │   ├── gemma_engine.py        # Tier 3 Gemma-4 GGUF engine
│   │   ├── gemma_onnx_engine.py   # Tier 2 PaliGemma ONNX engine
│   │   ├── onvif_service.py       # ONVIF auto-discovery & controls
│   │   └── pattern_engine.py      # Bounding box pattern processor (23 Rules)
│   ├── main.py                    # Server entrypoint & thread orchestrator
│   ├── requirements.txt           # Python library dependencies
│   └── video_validator.py         # Archive codec validation and repair tool
├── src/                           # React Electron Frontend Application
│   ├── components/                # Modular UI Components
│   │   ├── archive/               # Archive playback controls
│   │   ├── auth/                  # Illustrated login forms
│   │   ├── camera/                # WebRTC & MJPEG player interfaces
│   │   ├── configuration/         # Media, analytics, and zone polygon managers
│   │   ├── dashboard/             # Drag-and-Drop camera grids
│   │   ├── events/                # Live detections feed & RAG searches
│   │   └── layout/                # Global layout wrappers
│   ├── store/                     # Frontend state management (Zustand)
│   │   ├── cameraStore.js
│   │   └── userStore.js
│   ├── App.js                     # Main Tab Router & Universal Sidebar
│   ├── index.js                   # Web entrypoint
│   └── App.css                    # Main design system stylesheet
├── main.js                        # Electron desktop environment entrypoint
├── package.json                   # Node.js dependencies & Electron runner scripts
└── webpack.config.js              # Bundle packager settings
```

---

## 🚀 Getting Started

### 📋 Prerequisites

Ensure you have the following installed on your system:
* **Operating System:** Windows 10/11 (with PowerShell or cmd)
* **Python:** Version 3.12+ (64-bit)
* **Node.js & npm:** Node LTS versions
* **FFmpeg:** Installed and added to your system `PATH`
* **GPU (Optional):** NVIDIA GPU with CUDA Toolkit configured for accelerated model execution

---

### 💾 1. Backend Setup

1. Navigate to the `backend` directory:
   ```powershell
   cd backend
   ```
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install the dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Setup AI Models:
   * **Tier 1 Bounding Boxes:** Place `yolov8n.pt` and `yolo26n.pt` inside the `backend` directory.
   * **Tier 2 Semantic:** Download and export PaliGemma ONNX files into `backend/models/paligemma.onnx`.
   * **Tier 3 Vision LLM:** Place GGUF files (`gemma-4-E4B-it-Q4_K_M.gguf` & `mmproj-gemma-4-E4B-it-BF16.gguf`) in `backend/gemma-4-E4B-it-GGUF/` directory.

5. Copy the `.env.example` to `.env` and configure custom thresholds:
   ```powershell
   copy .env.example .env
   ```

6. Run the FastAPI server:
   ```powershell
   python main.py
   ```
   The backend will auto-load configured streams and host API services on `http://127.0.0.1:8000`.

---

### 💻 2. Frontend & Electron Setup

1. Return to the root directory:
   ```powershell
   cd ..
   ```
2. Install frontend dependencies:
   ```powershell
   npm install
   ```
3. Boot the application in Development Mode:
   ```powershell
   npm start
   ```
   This will simultaneously boot the React bundle server on `http://localhost:3000` and open the **Electron Desktop Window** displaying Eagle VMS.

---

## ⚙️ Configuration Structures

### 📹 Camera Ingestion Configuration (`backend/data/camera_configuration.json`)
Manage collections of cameras grouped under logical site keys:
```json
{
  "karnal": {
    "172.16.1.101": "rtsp://admin:password@172.16.1.101:554/h264Preview_01_main"
  },
  "delhi_headquarters": {
    "192.168.1.50": "rtsp://operator:secure123@192.168.1.50:554/live"
  }
}
```

### 📐 Zone & Polygon Coordinates (`backend/data/camera_zones.json`)
Saves normalized boundary coordinates drawn via the grid zone manager:
```json
{
  "172.16.1.101": [
    {
      "id": "zone_0",
      "name": "Restricted Lobby Boundary",
      "points": [
        {"x": 102, "y": 250},
        {"x": 305, "y": 250},
        {"x": 420, "y": 680},
        {"x": 80, "y": 680}
      ],
      "rules": [
        {
          "rule_id": 23,
          "name": "Zone Monitoring",
          "severity": "critical"
        }
      ]
    }
  ]
}
```

---

## 🚨 Automated Security Pattern Rules (23 Engine Core)

The `pattern_engine.py` runs continuous validation algorithms on bounding boxes and triggers cognitive analysis using one of 23 rule signatures:

| ID | Rule Name | Analysis Focus | Severity |
| :--- | :--- | :--- | :--- |
| **1** | Appearance Search | Detailed description matching of person/vehicle details | Low / Medium |
| **2** | Camera Tamper | Blurs, shifts, lens obscuring, hands blocking lens | High |
| **3** | Handbag Snatching | Rapid grabbing motion, distress reactions, fleeing targets | Critical |
| **4** | Crowd Detection | People count anomalies, stampede risks, agitation behavior | High |
| **5** | Eve Teasing / Harassment | Cornering, following, aggressive body language | Critical |
| **8** | Gesture Detection | Distress signals, waving for help, aggressive fist raising | Medium |
| **10** | Intrusion Detection | BBoxes breaching restricted perimeter spaces | High |
| **11** | Boundary Crossing | Cross-line detection of virtual boundary perimeters | High |
| **15** | People Fighting | Sudden physical alterations, punching, pushing, wrestling | Critical |
| **16** | Person Collapsing | Motionless bodies on ground, sudden falls | Critical |
| **19** | Unattended Object | Luggage, bags, boxes left without an owner nearby | High |
| **21** | Abduction Detection | Forced removal, child in distress, struggle behaviors | Critical |
| **23** | Zone Monitoring | Multi-point restricted boundary breaches (Active Alerts) | High / Critical |

---

## 🛠️ Troubleshooting & Diagnostics

### 1. RTSP Stream Failures / Timeout Logs
* **Symptom:** Bouncing grey screens, connection timeout logs in the terminal.
* **Fix:** Open `.env` and verify `RTSP_OPEN_TIMEOUT` and `RTSP_READ_TIMEOUT`. Check network firewalls and test the raw RTSP link in VLC Media Player. Eagle VMS will automatically test connections with 5 trial frames and swap from TCP to UDP if packet losses occur.

### 2. HEVC/H.265 Decoding Failures
* **Symptom:** Backend prints `fctx->async_lock failed` or stream drops repeatedly.
* **Fix:** The system automatically locks the thread context by setting `os.environ["OPENCV_FFMPEG_THREADS"] = "1"` during startup. Make sure your graphics driver supports HEVC hardware decoding or swap camera configuration encoder output to standard H.264.

### 3. Gemma engine is busy / Timeout skips
* **Symptom:** Tier 3 logs show skips or engine busy messages.
* **Fix:** If running on CPU, local LLM/VLM processing can take 15–30 seconds. Enable GPU acceleration by ensuring standard compilation of `llama-cpp-python` with CUDA support:
  ```powershell
  $env:CMAKE_ARGS="-DGGML_CUDA=on"
  pip install llama-cpp-python --force-reinstall --no-cache-dir
  ```

---

## ⚖️ License

Distributed under the ISC License. See `LICENSE` for details.