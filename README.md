# DroidBridge

ADB-powered Android device management tool. Faster file transfers than MTP,
a complete WhatsApp media analysis/backup/cleanup toolkit, storage analysis,
app management, and rich reports — all offline, no cloud, no telemetry.

See `docs/DroidBridge_Project_Document.md` for the full project specification.

## Status

Phase 1 (Foundation): ADB core wrapper and Device Manager.

## Requirements

- Python 3.10+
- ADB (bundled for Linux in `droidbridge/resources/platform-tools-linux/`,
  falls back to `adb` on PATH if not present)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
droidbridge device connect   # check ADB connection / device status
droidbridge device info      # show device info and storage breakdown
```

## Development

Tests are written with pytest and follow a TDD workflow:

```bash
pytest
```

## License

MIT — see [LICENSE](LICENSE).
