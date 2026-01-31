#!/bin/bash
# nas-sync.sh - Complete NAS sync setup (PC → NAS, one-way, no deletions)
# Fully safe for re-runs, mounts, and incremental syncs

set -e  # Exit immediately on error

echo "=== NAS Real-time Sync Setup ==="
echo

# ------------------------------------------------------------------
# 1. Install required packages
# ------------------------------------------------------------------
echo "Installing packages..."

sudo apt update
sudo apt install -y lsyncd cifs-utils

# ------------------------------------------------------------------
# 2. Create NAS mount points (safe to re-run)
# ------------------------------------------------------------------
echo "Creating mount points for local partitions..."

# key = partition label, value = fstype
declare -A PARTITION_FSTYPES=(
{%- for partition, fstype in partition_fstypes.items() %}
    ["{{ partition }}"]="{{ fstype }}"
{%- endfor %}
)

MNT_LOCAL={{ local_mount_path }}

for LABEL in "${!PARTITION_FSTYPES[@]}"; do
    sudo mkdir -p "${MNT_LOCAL}${LABEL}"
done

echo "Creating mount points for NAS folders..."

# key = partition label, value = nas path
declare -A PARTITION_NAS_PATHS=(
{%- for partition, nas_path in partition_nas_paths.items() %}
    ["{{ partition }}"]="{{ nas_path }}"
{%- endfor %}
)

MNT_NAS={{ nas_mount_path }}

for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    sudo mkdir -p "${MNT_NAS}${NAS_PATH}"
done

# ------------------------------------------------------------------
# 3. Prompt for NAS password and create credentials file (root-only readable)
# ------------------------------------------------------------------
echo "Creating credentials file..."

read -s -p "Enter NAS password: " NAS_PASS
echo
sudo bash -c "cat > /etc/samba/credentials" << EOF
username={{ nas_username }}
password=$NAS_PASS
EOF
sudo chmod 600 /etc/samba/credentials

# ------------------------------------------------------------------
# 4. Append fstab entries (dynamic UID/GID)
# ------------------------------------------------------------------
echo "Configuring /etc/fstab..."

USER_ID=$(id -u)
GROUP_ID=$(id -g)

REMOTE_BASE={{ nas_base_path }}

LOCAL_FSTAB_ENTRIES=""

for LABEL in "${!PARTITION_FSTYPES[@]}"; do
    FSTYPE="${PARTITION_FSTYPES[$LABEL]}"
    LOCAL_FSTAB_ENTRIES+="LABEL=${LABEL} ${MNT_LOCAL}${LABEL} ${FSTYPE} defaults,uid=$USER_ID,gid=$GROUP_ID,iocharset=utf8,nofail,x-systemd.automount 0 0"$'\n'
done

NAS_FSTAB_ENTRIES=""

for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    NAS="${REMOTE_BASE}${NAS_PATH}"
    LOCAL="${MNT_NAS}${NAS_PATH}"
    NAS_FSTAB_ENTRIES+="$NAS $LOCAL cifs credentials=/etc/samba/credentials,uid=$USER_ID,gid=$GROUP_ID,iocharset=utf8,file_mode=0777,dir_mode=0777,_netdev,nofail,x-systemd.automount,x-systemd.mount-timeout=10,x-systemd.device-timeout=10,x-gvfs-hide,vers=3.1.1 0 0"$'\n'
done

FSTAB_BEGIN="# BEGIN nas-sync-script-builder"
FSTAB_END="# END nas-sync-script-builder"

FSTAB_BLOCK="$FSTAB_BEGIN

# Local Drive Mounts

$LOCAL_FSTAB_ENTRIES

# NAS Sync Mounts

$NAS_FSTAB_ENTRIES

$FSTAB_END"

# Remove previously inserted block (safe for re-runs)
sudo sed -i "\|$FSTAB_BEGIN|,\|$FSTAB_END|d" /etc/fstab

# Trim trailing empty lines to prevent newline buildup on re-runs
sudo sed -i ':a;/^\n*$/{$d;N;ba}' /etc/fstab

# Append the fstab block with one blank line before and after
sudo bash -c "printf '\n%s\n' \"$FSTAB_BLOCK\" >> /etc/fstab"

# ------------------------------------------------------------------
# 5. Mount all configured filesystems
# ------------------------------------------------------------------
echo "Mounting NAS shares..."

sudo mount -a

# ------------------------------------------------------------------
# 6. One-time sync of files
#    - Safe to run multiple times
#    - Copies only missing/new files, preserves existing NAS files
# ------------------------------------------------------------------
echo "Syncing files to NAS..."

# ------------------------------------------------------------------
# rsync excludes for former Windows / NTFS partitions
# ------------------------------------------------------------------
EXCLUDE_ITEMS=(
{%- for item in exclude_items %}
    '{{ item }}'
{%- endfor %}
)

# Generate rsync array
RSYNC_EXCLUDES=()
for item in "${EXCLUDE_ITEMS[@]}"; do
    RSYNC_EXCLUDES+=( "--exclude=$item" )
done

# Generate Lua array for lsyncd
LUA_EXCLUDES=""
for item in "${EXCLUDE_ITEMS[@]}"; do
    LUA_EXCLUDES+="            \"$item\","$'\n'
done

# Sync all partitions
for LABEL in "${!PARTITION_NAS_PATHS[@]}"; do
    SRC="${MNT_LOCAL}${LABEL}/"
    DST="${MNT_NAS}${PARTITION_NAS_PATHS[$LABEL]}/"
    echo "Syncing new files from $SRC → $DST ..."
    rsync -a --update --info=progress2 "${RSYNC_EXCLUDES[@]}" "$SRC" "$DST"
done

echo "Initial sync complete."

# ------------------------------------------------------------------
# 7. Create lsyncd configuration (insist=true ensures retries if NAS temporarily unavailable)
# ------------------------------------------------------------------
echo "Creating lsyncd configuration..."

SYNC_LINES=""
for LABEL in "${!PARTITION_NAS_PATHS[@]}"; do
    SRC="${MNT_LOCAL}${LABEL}/"
    DST="${MNT_NAS}${PARTITION_NAS_PATHS[$LABEL]}/"
    SYNC_LINES+="syncDir(\"$SRC\", \"$DST\")"$'\n'
done

sudo mkdir -p /etc/lsyncd

sudo bash -c "cat > /etc/lsyncd/lsyncd.conf.lua" << EOF
settings {
    logfile = "/var/log/lsyncd/lsyncd.log",
    statusFile = "/var/log/lsyncd/lsyncd.status",
    statusInterval = 20,
    maxProcesses = 4,
    insist = true,
}

function syncDir(sourceDir, targetDir)
    sync {
        default.rsync,
        source = sourceDir,
        target = targetDir,
        delete = false,
        exclude = {
$LUA_EXCLUDES
        },
        rsync = {
            archive = true
        }
    }
end

$SYNC_LINES
EOF

# ------------------------------------------------------------------
# 8. Configure lsyncd systemd dependencies (wait for all mounts)
# ------------------------------------------------------------------
echo "Configuring lsyncd systemd dependencies..."

sudo mkdir -p /etc/systemd/system/lsyncd.service.d/

REQUIRES_MOUNTS_FOR=""

# Include mounted partitions
for LABEL in "${!PARTITION_FSTYPES[@]}"; do
    REQUIRES_MOUNTS_FOR+="${MNT_LOCAL}${LABEL} "
done

# Include mounted NAS paths
for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    REQUIRES_MOUNTS_FOR+="${MNT_NAS}${NAS_PATH} "
done

# Write systemd override.conf using the generated line
sudo bash -c "cat > /etc/systemd/system/lsyncd.service.d/override.conf" << EOF
[Unit]
After=local-fs.target remote-fs.target network-online.target
RequiresMountsFor=$REQUIRES_MOUNTS_FOR

[Service]
Restart=on-failure
RestartSec=10
EOF

# ------------------------------------------------------------------
# 9. Ensure lsyncd log directory exists
# ------------------------------------------------------------------
echo "Creating log directory..."

sudo mkdir -p /var/log/lsyncd

# ------------------------------------------------------------------
# 10. Configure log rotation for lsyncd
# ------------------------------------------------------------------
echo "Creating logrotate configuration for lsyncd..."

sudo bash -c 'cat > /etc/logrotate.d/lsyncd' << 'EOF'
/var/log/lsyncd/*.log /var/log/lsyncd/*.status {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    copytruncate
}
EOF

# ------------------------------------------------------------------
# 11. Increase inotify max_user_watches (for large directories)
# ------------------------------------------------------------------
echo "Setting fs.inotify.max_user_watches to 524288..."

# Apply immediately for current session
sudo sysctl -w fs.inotify.max_user_watches=524288

# Make persistent across reboots
sudo bash -c 'echo "fs.inotify.max_user_watches=524288" > /etc/sysctl.d/99-inotify.conf'

echo "Current max_user_watches: $(cat /proc/sys/fs/inotify/max_user_watches)"

# ------------------------------------------------------------------
# 12. Enable and start lsyncd
# ------------------------------------------------------------------
echo "Starting lsyncd service..."

sudo systemctl daemon-reload
sudo systemctl enable lsyncd
sudo systemctl restart lsyncd

# ------------------------------------------------------------------
# 13. Final status output
# ------------------------------------------------------------------
echo
echo "=== Setup Complete ==="
echo
echo "Checking lsyncd status..."

sudo systemctl status lsyncd --no-pager

# ------------------------------------------------------------------
# 14. Useful commands
# ------------------------------------------------------------------
echo
echo "To monitor sync:"
echo "  sudo tail -f /var/log/lsyncd/lsyncd.log"
echo "  sudo cat /var/log/lsyncd/lsyncd.status"
echo
echo "To check mounts:"
echo "  mount | grep synologynas"
