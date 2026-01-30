from pydbus import SystemBus
from typing import Dict

def detect_partition_fstypes() -> Dict[str, str]:
    bus = SystemBus()
    udisks = bus.get("org.freedesktop.UDisks2")
    objects = udisks.GetManagedObjects()

    partition_fstypes: Dict[str, str] = {}

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

        partition_fstypes[label] = fstype

        #uuid = block.get("IdUUID")
        #device = b2s(block["Device"])

        #partitions[label] = {
        #    "label": label,
        #    "fstype": fstype,
        #    "uuid": uuid,
        #    "device": device,
        #}

    return partition_fstypes


def get_partition_nas_paths(partition_fstypes: Dict[str, str]) -> Dict[str, str]:
    return {label: label for label in partition_fstypes}
