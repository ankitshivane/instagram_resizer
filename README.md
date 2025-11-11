# Instagram Photo Resizer (Offline Desktop App)

A secure, offline desktop application built in **Python + Tkinter + Pillow** for resizing photos for Instagram and other social platforms — **without cropping or losing clarity**.

---

## 🚀 Features

✅ **No Internet Required** — runs completely offline, no data upload.  
✅ **Fit / Fill / Stretch** resize modes.  
✅ **Aspect Ratios:** 1:1, 4:5, 9:16, 16:9, 3:2, or custom.  
✅ **Background Fill:** solid color or blurred background.  
✅ **Watermark Options:** optional text or logo watermark.  
✅ **Batch Processing:** resize entire folders or multiple photos at once.  
✅ **Drag & Drop Support:** easily add images to the list.  
✅ **Preview before Saving.**  
✅ **High-quality resize (Lanczos filter).**  
✅ **One-click `.exe` build for Windows.**

---

## 🧠 How It Works

- **Fit Mode (default):** Keeps the full image visible, adds padding/background to fit target ratio — no cropping.  
- **Fill Mode:** Crops the image slightly to fill the aspect ratio completely.  
- **Stretch Mode:** Distorts the image to fill the chosen ratio.  

---

## 🧰 Tech Stack

- **Language:** Python 3.10+  
- **GUI Framework:** Tkinter  
- **Image Processing:** Pillow (PIL)  
- **Optional:** tkinterdnd2 for drag-and-drop  
- **Build Tool:** PyInstaller  

---

### Setup (one-time)

- Install Python 3.10+ and ensure python on PATH. 
- Create project folder and virtualenv:
```commandline
mkdir instagram_resizer
cd instagram_resizer
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
# source venv/bin/activate
pip install --upgrade pip

```

- Install required Python packages:
```commandline
pip install pillow
```


Optional: For improved drag-and-drop on some systems you can install tkinterdnd2, but the app will work without it. To install:
```commandline
pip install tkinterdnd2
```

## ⚙️ Installation

1. Clone or download this repository:
   ```bash
   git clone https://github.com/ankitshivane/instagram_resizer.git
   cd instagram-photo-resizer

2. Create and activate a virtual environment:
```bash
python -m venv venv
venv\Scripts\activate       # Windows
# or
source venv/bin/activate    # macOS / Linux
```
3. Install dependencies:
```commandline
pip install pillow tkinterdnd2
```

🖥️ Run the Application
```commandline
python app.py
```

---
## 🔐 Privacy Note

This tool performs all operations locally — no internet access, no uploads.
Your images stay on your computer at all times.

---

## 📜 License

MIT License © 2025 Ankit Shivane