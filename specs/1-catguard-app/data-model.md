# Data Model: CatGuard App

**Phase**: 1 — Design  
**Date**: 2026-02-28  
**Source**: [spec.md](spec.md), [research.md](research.md)

---

## Entities

### 1. Settings

Persisted as `settings.json` in the platform user config directory.

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `camera_index` | `int` | `0` | ≥ 0 | Index of the webcam to use |
| `confidence_threshold` | `float` | `0.40` | [0.0, 1.0] | YOLO detection confidence; higher = fewer false positives |
| `cooldown_seconds` | `float` | `15.0` | > 0 | Minimum seconds between consecutive alerts |
| `sound_library_paths` | `list[str]` | `[]` | Existing files only | Absolute paths to user-uploaded MP3/WAV files |
| `autostart` | `bool` | `False` | — | Whether the app starts on user login |

**Validation rules**:
- `sound_library_paths`: stale (non-existent) paths are silently dropped on load.
- If config file is missing or corrupt, defaults are written and used.
- Writes are atomic (`.tmp` rename) to prevent corrupt state on crash.

---

### 2. DetectionEvent

In-memory only; never written to disk. Used for logging and cooldown management.

| Field | Type | Description |
|---|---|---|
| `timestamp` | `datetime` | UTC timestamp of the detection |
| `confidence` | `float` | YOLO confidence score (0.0–1.0) |
| `action` | `DetectionAction` | Outcome of the detection (see enum below) |
| `sound_file` | `str \| None` | Filename of the sound played, or `None` if suppressed |

**DetectionAction enum**:
- `SOUND_PLAYED` — alert was triggered and a sound was played
- `COOLDOWN_SUPPRESSED` — cat detected but cooldown period had not elapsed; no sound

---

### 3. SoundFile

Represents an audio file in the user's sound library.

| Field | Type | Description |
|---|---|---|
| `path` | `Path` | Absolute file path |
| `name` | `str` | Display name (filename without extension) |
| `format` | `str` | `"mp3"` or `"wav"` |

**Built-in default**: A `default.wav` bundled with the app at `assets/sounds/default.wav`. Always available; used when `sound_library_paths` is empty.

---

### 4. Camera

Represents a detected webcam. Enumerated at startup and in the Settings window.

| Field | Type | Description |
|---|---|---|
| `index` | `int` | OpenCV camera index (0, 1, 2, …) |
| `name` | `str` | Display label (e.g., `"Camera 0"`, `"HD Webcam"`) |
| `available` | `bool` | Whether the camera was successfully opened |

---

### 5. AutostartState

Runtime view of the current autostart registration status. Not persisted (derived from filesystem).

| Field | Type | Description |
|---|---|---|
| `enabled` | `bool` | Whether autostart is currently registered |
| `platform` | `str` | `"Windows"`, `"Darwin"`, or `"Linux"` |
| `path` | `Path` | Path to the `.lnk` / `.plist` / `.desktop` file |

---

## State Machine: App Monitoring Lifecycle

```
            ┌─────────┐
  [startup] │  IDLE   │
   ─────────►         │
            └────┬────┘
                 │ [user clicks Start / autostart]
                 ▼
            ┌─────────────┐
   ┌────────►  MONITORING │◄──────────────────────────────────┐
   │        └─────┬───────┘                                   │
   │              │ [YOLO: cat detected]                       │
   │              ▼                                            │
   │        ┌─────────────┐                                    │
   │        │  DETECTING  │ ─[confidence < threshold]──────────┤
   │        └─────┬───────┘                                    │
   │              │ [confidence ≥ threshold]                   │
   │        ┌─────▼────────────────────────┐                  │
   │        │ cooldown elapsed?            │                   │
   │        └────┬─────────────────────────┘                  │
   │             │ YES                   │ NO                  │
   │             ▼                       ▼                     │
   │        ┌──────────┐        ┌──────────────────┐          │
   │        │ ALERTING │        │ COOLDOWN_SKIP     │──────────┘
   │        │(play snd)│        │(log suppressed)   │
   │        └────┬─────┘        └──────────────────-┘
   │             │ [sound started]
   │             ▼
   │        ┌──────────┐
   └────────│ COOLDOWN │
            │ (timer)  │
            └──────────┘
                 │ [cooldown expires]
                 └──────────────────► MONITORING
```

---

## Relationships

```
Settings ──── sound_library_paths ────► SoundFile (0..*)
Settings ──── camera_index ───────────► Camera (1)
DetectionEvent ──── sound_file ───────► SoundFile (0..1)
AutostartState ──── enabled ──────────► Settings.autostart (mirrors)
```

---

## Config Schema Version

The `settings.json` file is implicitly versioned. Any future breaking change to the schema MUST include:
1. A `schema_version` field added to `Settings`.
2. A migration function in `config.py` that upgrades old configs on load.
3. Updated `contracts/config.md` with the new schema.
