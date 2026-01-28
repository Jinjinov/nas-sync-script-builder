import argparse
from pathlib import Path
from .config import load_config
from .template import render_script

def main():
    parser = argparse.ArgumentParser(description="Generate NAS sync script")
    parser.add_argument("-c", "--config", type=Path, default=Path("nas_sync_config.yaml"))
    parser.add_argument("-o", "--output", type=Path, default=Path("nas-sync.sh"))
    parser.add_argument("--detect", action="store_true", help="Detect partitions automatically")
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.detect:
        from .partitions import detect_partitions, get_sync_dirs
        cfg.partitions = detect_partitions()
        cfg.sync_dirs = get_sync_dirs(cfg.partitions)

    script = render_script(cfg)
    
    args.output.write_text(script + "\n")
    args.output.chmod(0o755)

    print(f"Script written to {args.output}")
