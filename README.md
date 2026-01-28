# nas-sync-script-builder

Python GUI tool to generate a bash script for one-way, no-deletion NAS sync using `rsync` and `lsyncd`.

The script is idempotent and safe to re-run.

The script sets up a one way sync with no deletions, not a mirror.

Features:
- Automatic detection of eligible local partitions via UDisks2 (D-Bus)
- One-way sync only (local → NAS)
- No deletions on destination
- Initial sync using rsync --update
- Real-time sync via lsyncd
- Safe mount handling with systemd automounts
- Persistent credentials handling
- Configurable exclude patterns

## Requirements

System (Linux)
- systemd
- udisks2
- CIFS/SMB-compatible NAS (e.g. Synology)

The generated script installs these automatically:
- lsyncd
- cifs-utils

## Running the GUI

Install:
```
pip install nas-sync-script-builder
```

Run:
```
nas-sync-script-builder
```

This opens the GUI where you can:
- Review detected partitions
- Edit filesystem types if needed
- Configure NAS connection details
- Customize exclude patterns
- Adjust local → NAS directory mappings

Click **Generate** to:
- Save settings to `nas_sync_config.yaml`
- Generate the bash script `nas-sync.sh`

## Running the Generated Script

```
sudo ./nas-sync.sh
```

The script will:
- Install required system packages
- Prompt once for the NAS password and create `/etc/samba/credentials`
- Create mount points for local disks and NAS shares
- Configure mounts in `/etc/fstab`
- Perform an initial sync
- Configure lsyncd in `/etc/lsyncd/lsyncd.conf.lua`
- Configure lsyncd systemd dependencies in `/etc/systemd/system/lsyncd.service.d/override.conf`
- Configure lsyncd log rotation in `/etc/logrotate.d/lsyncd`
- Increase inotify max_user_watches in `/etc/sysctl.d/99-inotify.conf`
- Enable and start lsyncd

## Development

Use a virtual environment:
```
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:
```
pip install PySide6 Jinja2 PyYAML pydbus
```

System Dependencies for D-Bus (pydbus / PyGObject):

Required by PyGObject:
```
sudo apt install libgirepository-2.0-dev libcairo2-dev pkg-config
```

Required by pydbus:
```
pip install PyGObject
```

Editable install:
```
pip install -e .
```

Install the build tools:
```
pip install build twine
```

Create the distribution files:
```
python -m build
```

Check the distribution files:
```
twine check dist/*
```

Upload to TestPyPI:
```
twine upload --repository testpypi dist/*
```

https://test.pypi.org/project/nas-sync-script-builder/

Install from TestPyPI:
```
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ nas-sync-script-builder

```

Upload to PyPI:
```
twine upload dist/*
```

https://pypi.org/project/nas-sync-script-builder/

Install from PyPI:
```
pip install nas-sync-script-builder
```
