from pathlib import Path
import yaml
from typing import Dict, List
from .constants import DEFAULT_EXCLUDE_ITEMS

class NasSyncConfig:
    def __init__(
        self,
        nas_base_path: str,
        nas_username: str,
        nas_mount_path: str,
        local_mount_path: str,
        *,
        exclude_items: List[str] = None,
        partitions: Dict[str, str] = None,
        sync_dirs: Dict[str, str] = None,
    ):
        self.nas_base_path = nas_base_path
        self.nas_username = nas_username
        self.nas_mount_path = nas_mount_path
        self.local_mount_path = local_mount_path

        self.exclude_items = exclude_items or DEFAULT_EXCLUDE_ITEMS.copy()
        self.partitions = partitions or {}
        self.sync_dirs = sync_dirs or {}

    @classmethod
    def defaults(cls):
        return cls(
            nas_base_path="//synologynas.local/Intel-i5-2500/",
            nas_username="Jinjinov",
            nas_mount_path="/mnt/nas/",
            local_mount_path="/mnt/data/",
        )

def load_config(path: Path) -> NasSyncConfig:
    if not path.exists():
        return NasSyncConfig.defaults()

    data = yaml.safe_load(path.read_text()) or {}
    cfg = NasSyncConfig.defaults()

    for key in ["nas_base_path", "nas_username", "nas_mount_path", "local_mount_path", "exclude_items", "partitions", "sync_dirs"]:
        if key in data:
            setattr(cfg, key, data[key])

    return cfg

def save_config(cfg: NasSyncConfig, path: Path):
    data = {
        "nas_base_path": cfg.nas_base_path,
        "nas_username": cfg.nas_username,
        "nas_mount_path": cfg.nas_mount_path,
        "local_mount_path": cfg.local_mount_path,
        "exclude_items": cfg.exclude_items,
        "partitions": cfg.partitions,
        "sync_dirs": cfg.sync_dirs,
    }
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
