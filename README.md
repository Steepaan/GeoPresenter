# 🌍 GeoPresenter — Interactive Travel Photo & Map Viewer

A lightweight, presenter-ready web application designed for travel talks, lectures, and photo exhibitions. Built with **Python**, **Leaflet.js**, and the **MapTiler API**.

GeoPresenter automatically scans folders with travel photos and videos, extracts geographic EXIF metadata, and presents your media alongside an interactive map with adaptive motion and a regional overview minimap.

---

## ✨ Features

- **Automatic Album Tiles**: Scans a directory of media folders and creates a dashboard with custom cover images and item counts for each chapter.
- **EXIF GPS Extraction**: Automatically reads coordinates and capture dates from image metadata.
- **Asynchronous Reverse Geocoding**: Queries the MapTiler Geocoding API for English location names with instant request cancellation (`AbortController`) to avoid rate limits during fast browsing.
- **Adaptive Camera Navigation**:
  - **No camera movement** for consecutive photos taken within 50 meters.
  - **Smooth pan (`panTo`)** for nearby points (< 5 km) within a city or valley.
  - **High-altitude flyover (`flyTo`)** for longer journeys across regions.
- **Integrated Country Overview (Minimap)**: A secondary overview map in the bottom-right corner displays the overall location in the context of the whole country or island.
- **Video & Photo Support**: Supports `.jpg`, `.png`, `.webp`, `.mp4`, and `.mov` files with clean media switching and no memory leaks.
- **Presenter Controls**:
  - Toggle map visibility on and off (`M`) to expand images across the full screen.
  - Instant screen blackout (`B`) to redirect audience attention to the speaker.
  - Conflict-free video playback via `Space`.
- **Graceful Shutdown**: Shuts down the local Python HTTP server via a dedicated exit button in the UI.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- A free account on [MapTiler Cloud](https://cloud.maptiler.com/) to obtain an API key.

---

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/geo-presenter.git
   cd geo-presenter
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application:**

   Copy `config.example.json` to `config.json`.

   **Windows (PowerShell):**

   ```powershell
   Copy-Item config.example.json config.json
   ```

   **Linux / macOS:**

   ```bash
   cp config.example.json config.json
   ```

   Open `config.json` and set your MapTiler API key and the path to your media directory:

   ```json
   {
     "maptiler_key": "YOUR_MAPTILER_API_KEY",
     "photos_dir": "D:\\Photos\\MyTrip"
   }
   ```

4. **Launch the presenter:**

   ```bash
   python presenter.py
   ```

   The application will start the local HTTP server and automatically open your default browser. Press `F11` to enter full-screen mode.

---

## ⌨️ Controls & Shortcuts

| Key / Action | Function |
| --- | --- |
| `→` / `PageDown` | Next slide / video |
| `←` / `PageUp` | Previous slide / video |
| `Space` | Play / Pause active video |
| `M` | Toggle map visibility (Full-screen media mode) |
| `B` | Blank / Blackout screen |
| `Esc` | Return to album selection dashboard |
| **Exit Button** | Safely shuts down the local Python server and exits |

---

## 📁 Recommended Folder Structure

Place your media files into subfolders representing individual chapters or locations:

```text
MyTrip/
├── 01_Taipei/
│   ├── IMG_1001.JPG
│   ├── IMG_1002.JPG
│   └── clip_city.mp4
├── 02_Alishan/
│   ├── IMG_2001.JPG
│   └── IMG_2002.JPG
└── 03_Sun_Moon_Lake/
    └── IMG_3001.JPG
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
