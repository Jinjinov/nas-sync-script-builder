from pydbus import SystemBus
from typing import Dict

def detect_partitions() -> Dict[str, str]:
    """
    Detect mounted or unmounted filesystem partitions using UDisks2 via D-Bus.
    Returns a dict mapping partition label -> filesystem type.
    Ignores system partitions like /, /boot, /usr, /var.
    """
    bus = SystemBus()
    udisks = bus.get("org.freedesktop.UDisks2")
    objects = udisks.GetManagedObjects()

    partitions: Dict[str, str] = {}

    def b2s(b: bytes) -> str:
        return bytes(b).decode(errors="ignore").strip("\x00")

    for path, interfaces in objects.items():
        block = interfaces.get("org.freedesktop.UDisks2.Block")
        if not block:
            continue

        # Skip ignored devices
        if block.get("HintIgnore", False):
            continue
        if block.get("IdUsage") != "filesystem":
            continue

        fstype = block.get("IdType")
        if not fstype:
            continue

        fs = interfaces.get("org.freedesktop.UDisks2.Filesystem")
        mounted = bool(fs and fs.get("MountPoints"))
        if mounted:
            mountpoints = [b2s(mp) for mp in fs["MountPoints"]]
            if any(mp in ("/", "/boot", "/usr", "/var") for mp in mountpoints):
                continue

        label = block.get("IdLabel")
        if not label:
            continue

        partitions[label] = fstype

    return partitions


def get_sync_dirs(partitions: Dict[str, str]) -> Dict[str, str]:
    """
    Create default sync mapping: local disk label -> NAS path.
    Initially mirrors label -> label.
    """
    return {label: label for label in partitions}
