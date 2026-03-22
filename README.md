# CatGuard

CatGuard watches your table with a webcam and plays an alert sound when it detects a cat to scare it away.

## Features

- Detects cats on your table or desk and plays an alert to scare them away.
- Runs in the system tray for quick access to the app functionality.
- Shows a live camera view with cat detection overlays.
- Lets you choose the camera and tune detection sensitivity, cooldown, and detection FPS.
- Supports the built-in alert sound, your own MP3/WAV files, and microphone-recorded custom alerts.
- Can play one specific alert sound or rotate randomly through your sound library.
- Supports optional start at login and daily monitoring schedules.
- Lets you take clean photos from the live view, with an optional countdown before capture.
- Saves dated tracking screenshots for later review.
- Tracks the full duration of each cat visit and records whether the alert worked, giving you a clear picture of how your cat responds over time.

## Interesting Facts

- The default sound is "Tom spells CAT" from [Tom and Jerry Online](https://www.tomandjerryonline.com/sounds.cfm).
- Not a single line of Python code was written by a human.
- It works! :-)

## Download

Pre-built executables are available on the [Releases](../../releases) page. No Python installation is required.

1. Go to **Releases** and download the zip for your platform:
   - `catguard-{version}-windows.zip`
   - `catguard-{version}-macos.zip`
   - `catguard-{version}-linux.zip`
2. Extract the zip.
3. Run the executable inside the `catguard/` folder:
   - **Windows**: `catguard\catguard.exe`
   - **macOS / Linux**: `./catguard/catguard`

On first launch, CatGuard downloads the YOLO model (`~6 MB`) and caches it locally. Internet access is required only once.

## Getting Started

1. Launch CatGuard.
2. Find the CatGuard icon in your system tray or menu bar.
3. Open `Settings…` to choose your camera, alert sound, schedule, and save locations.
4. Use `Live View` to show the live camera window.
5. Use `Pause` / `Continue` when you want to stop or resume monitoring without quitting the app.

## OS Security Warnings

**Windows - SmartScreen**

Because the executable is not code-signed, Windows may show a SmartScreen warning.
To allow it: right-click the `.exe` -> **Properties** -> check **Unblock** -> **OK**, then run again.
Alternatively, click **More info** -> **Run anyway** in the SmartScreen dialog.

**macOS - Gatekeeper**

macOS blocks unsigned apps by default.
To allow it: open **System Settings** -> **Privacy & Security** -> scroll to the blocked app -> click **Open Anyway**.

## Development

For source setup, testing, and build instructions, see [DEVELOPMENT.md](DEVELOPMENT.md).
