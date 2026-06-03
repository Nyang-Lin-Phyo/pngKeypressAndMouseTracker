# PNGvtuber Overlay

Simple PNG vtuber overlay for OBS using a browser source and a local WebSocket server.

## Features

* Keyboard-triggered PNG expressions
* Mouse-following hand overlay
* OBS browser source compatible
* Standalone Windows executable via PyInstaller

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the launcher:

```bash
python launcher.py
```

or run:

```text
PNGvtuber Launcher.exe
```

3. Select your PNG folder and launch the server.

4. Add the browser source to OBS:

```text
pngvtuber-overlay.html
```

Recommended size:

```text
1920 x 1080
```

## Required PNG Files

```text
base.png
rightHandMouse.png

press1.png
press2.png
press3.png
press4.png

pressQ.png
pressW.png
pressE.png
pressR.png

pressA.png
pressS.png
pressD.png
pressF.png

pressSpace.png
```

## Build

Activate the virtual environment and run:

```powershell
.\build.bat
```

The executable will be generated in:

```text
dist/
```
