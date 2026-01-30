from jinja2 import Environment, PackageLoader
from .config import NasSyncConfig

#env = Environment(
#    loader=FileSystemLoader(Path(__file__).parent / "templates"),
#    lstrip_blocks=False,
#    trim_blocks=False,
#)
env = Environment(
    loader=PackageLoader("nas_sync_script_builder", "templates"),
    autoescape=False, # shell scripts don't need HTML escaping
    lstrip_blocks=False,
    trim_blocks=False,
)

template = env.get_template("nas-sync.sh.tpl")

def render_script(cfg: NasSyncConfig) -> str:
    return template.render(
        nas_base_path=cfg.nas_base_path.rstrip("/") + "/",
        nas_username=cfg.nas_username,
        nas_mount_path=cfg.nas_mount_path.rstrip("/") + "/",
        local_mount_path=cfg.local_mount_path.rstrip("/") + "/",
        exclude_items=cfg.exclude_items,
        partition_fstypes=cfg.partition_fstypes,
        partition_nas_paths=cfg.partition_nas_paths,
    )
