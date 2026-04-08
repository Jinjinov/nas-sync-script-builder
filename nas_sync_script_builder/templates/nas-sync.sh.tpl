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
# lsyncd:     monitors directories for changes and triggers rsync automatically in real-time
# cifs-utils: provides tools to mount Windows/SMB network shares (needed for NAS CIFS mounts)
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

MNT_LOCAL="{{ local_mount_path }}"

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

MNT_NAS="{{ nas_mount_path }}"

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

USER_ID=${SUDO_UID:-$(id -u)}
GROUP_ID=${SUDO_GID:-$(id -g)}

REMOTE_BASE="{{ nas_base_path }}"

LOCAL_FSTAB_ENTRIES=""

for LABEL in "${!PARTITION_FSTYPES[@]}"; do
    FSTYPE="${PARTITION_FSTYPES[$LABEL]}"
    LOCAL_FSTAB_ENTRIES+="LABEL=${LABEL} ${MNT_LOCAL}${LABEL} ${FSTYPE} uid=$USER_ID,gid=$GROUP_ID,nofail 0 0"$'\n'
done

NAS_FSTAB_ENTRIES=""

# _netdev: tells systemd this is a network device mount, so it waits for the network before mounting
# nofail:  don't halt boot if the NAS is unreachable
# noac:    disables CIFS attribute caching so rsync always reads fresh timestamps from the NAS.
#          Without this, the CIFS client caches stale timestamps (the rename time instead of the
#          original mtime), causing rsync to think files differ and re-upload them on every restart.

for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    NAS="${REMOTE_BASE}${NAS_PATH}"
    LOCAL="${MNT_NAS}${NAS_PATH}"
    NAS_FSTAB_ENTRIES+="$NAS $LOCAL cifs credentials=/etc/samba/credentials,uid=$USER_ID,gid=$GROUP_ID,file_mode=0777,dir_mode=0777,_netdev,nofail,noac 0 0"$'\n'
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
# rsync excludes
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
# -a:             archive mode: recursive, preserves symlinks, timestamps, owner, group
# --update:       skip files where the destination is newer than the source
# --size-only:    skip files where size matches, ignoring timestamps (CIFS timestamps are unreliable)
# --no-perms:     don't sync Unix permissions (CIFS ignores them anyway, reports false differences)
# --info=progress2: show overall transfer progress instead of per-file

for LABEL in "${!PARTITION_NAS_PATHS[@]}"; do
    SRC="${MNT_LOCAL}${LABEL}/"
    DST="${MNT_NAS}${PARTITION_NAS_PATHS[$LABEL]}/"
    echo "Syncing new files from $SRC → $DST ..."
    rsync -a --update --size-only --no-perms --info=progress2 "${RSYNC_EXCLUDES[@]}" "$SRC" "$DST"
done

echo "Initial sync complete."

# ------------------------------------------------------------------
# 7. Create lsyncd configuration
# ------------------------------------------------------------------
echo "Creating lsyncd configuration..."

SYNC_LINES=""
for LABEL in "${!PARTITION_NAS_PATHS[@]}"; do
    SRC="${MNT_LOCAL}${LABEL}/"
    DST="${MNT_NAS}${PARTITION_NAS_PATHS[$LABEL]}/"
    SYNC_LINES+="syncDir(\"$SRC\", \"$DST\")"$'\n'
done

LUA_MOUNT_CHECKS=""
for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    FULL_PATH="${MNT_NAS}${NAS_PATH}"
    LUA_MOUNT_CHECKS+="if not is_mounted(\"$FULL_PATH\") then error(\"NAS mount not available: $FULL_PATH\") end"$'\n'
done

sudo mkdir -p /etc/lsyncd

# never delete files on NAS even if deleted on PC with "delete = false"

sudo bash -c "cat > /etc/lsyncd/lsyncd.conf.lua" << EOF
local function is_mounted(path)
    local f = io.popen("mountpoint -q " .. path .. " && echo yes || echo no")
    local result = f:read("*l")
    f:close()
    return result == "yes"
end

$LUA_MOUNT_CHECKS

settings {
    logfile = "/var/log/lsyncd/lsyncd.log",
    statusFile = "/var/log/lsyncd/lsyncd.status",
    statusInterval = 20,
    maxProcesses = 4,
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
            archive = true,
            perms = false,
            _extra = {"--size-only"}
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

LOCAL_MOUNTS_FOR=""

# Include mounted partitions (RequiresMountsFor only, no BindsTo)
for LABEL in "${!PARTITION_FSTYPES[@]}"; do
    LOCAL_MOUNTS_FOR+="${MNT_LOCAL}${LABEL} "
done

BINDS_TO_MOUNTS=""

# Include NAS mounts as systemd unit names (for Requires= + BindsTo= + After=)
for NAS_PATH in "${PARTITION_NAS_PATHS[@]}"; do
    FULL_PATH="${MNT_NAS}${NAS_PATH}"
    # Convert path to systemd unit name: strip leading /, replace / with -
    UNIT_NAME="$(echo "${FULL_PATH#/}" | tr '/' '-').mount"
    BINDS_TO_MOUNTS+="$UNIT_NAME "
done

# Write systemd override.conf using the generated lines

# After=              start lsyncd only after network, local drives, and NAS mounts are up
# RequiresMountsFor=  ensure local NTFS drives are mounted before starting
# Requires=           if any NAS mount unit stops, stop lsyncd too
# BindsTo=            stronger than Requires=: if a NAS mount drops mid-run, stop lsyncd immediately

sudo bash -c "cat > /etc/systemd/system/lsyncd.service.d/override.conf" << EOF
[Unit]
After=local-fs.target remote-fs.target network-online.target $BINDS_TO_MOUNTS
RequiresMountsFor=$LOCAL_MOUNTS_FOR
Requires=$BINDS_TO_MOUNTS
BindsTo=$BINDS_TO_MOUNTS

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

# weekly:       rotate logs once a week
# rotate 4:     keep 4 weeks of logs
# compress:     gzip rotated logs
# missingok:    don't error if log file is missing
# notifempty:   don't rotate empty logs
# copytruncate: copy then truncate instead of renaming (safe for running processes)

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
echo "Useful commands:"
echo "  # check if lsyncd process is running"
echo "  ps aux | grep [l]syncd"
echo
echo "  # last 500 lines of lsyncd log"
echo "  sudo tail -n 500 /var/log/lsyncd/lsyncd.log"
echo
echo "  # current sync status"
echo "  sudo cat /var/log/lsyncd/lsyncd.status"
echo
echo "  # last 500 lines of systemd journal"
echo "  sudo journalctl -u lsyncd -n 500 --no-pager"
