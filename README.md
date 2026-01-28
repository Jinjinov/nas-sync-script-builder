# nas-sync-script-builder

Python GUI tool to generate bash scripts for one-way, no-deletion NAS sync using `rsync` and `lsyncd`.

The generated script:
- Mounts local disks and NAS shares
- Performs an initial non-destructive sync (PC → NAS)
- Sets up real-time syncing using lsyncd
- Is idempotent and safe to re-run
- Never deletes files on the NAS

## Features

Automatic detection of local filesystem partitions via UDisks2 (D-Bus)  
One-way sync only (local → NAS)  
No deletions on destination  
Initial sync using rsync --update  
Real-time sync via lsyncd  
Safe mount handling with systemd automounts  
Persistent credentials handling  
Configurable exclude patterns  

## How It Works

The Python GUI:
- Detects eligible local partitions
- Lets you define local → NAS directory mappings
- Lets you configure exclude patterns
- Saves all settings
- Generates a Bash script

The generated Bash script:
- Installs required system packages
- Creates mount points
- Mounts local disks and NAS shares
- Performs an initial rsync
- Configures and starts lsyncd
- Sets up logging, log rotation, and systemd dependencies

## Requirements

System (Linux)
- systemd
- udisks2
- CIFS/SMB-compatible NAS (e.g. Synology)

The generated script installs these automatically:
- lsyncd
- cifs-utils

## Python Environment

It is strongly recommended to use a virtual environment.

```
python3 -m venv venv
source venv/bin/activate
```

Install Python dependencies:

```
pip install PySide6 Jinja2 PyYAML pydbus
```

### System Dependencies for D-Bus (pydbus / PyGObject)

Required by PyGObject:

```
sudo apt install libgirepository-2.0-dev libcairo2-dev pkg-config
```

Required by pydbus:

```
pip install PyGObject
```

## Running the GUI

```
python3 nas_sync_script_builder.py
```

This opens the GUI where you can:
- Review detected partitions
- Edit filesystem types if needed
- Configure NAS connection details
- Customize exclude patterns
- Adjust local → NAS directory mappings

Click **Generate** to:
- Persist settings to `nas_sync_config.yaml`
- Generate the bash script `nas-sync.sh`

## Running the Generated Script

```
sudo ./nas-sync.sh
```

What it will do:
- Prompt once for the NAS password and create `/etc/samba/credentials`
- Configure mounts in `/etc/fstab`
- Perform an initial sync
- Configure lsyncd in `/etc/lsyncd/lsyncd.conf.lua`
- Configure lsyncd systemd dependencies in `/etc/systemd/system/lsyncd.service.d/override.conf`
- Configure lsyncd log rotation in `/etc/logrotate.d/lsyncd`
- Increase inotify max_user_watches in `/etc/sysctl.d/99-inotify.conf`
- Enable and start lsyncd

The script is safe to run multiple times.

This is designed as a one way sync with no deletions, not a mirror.