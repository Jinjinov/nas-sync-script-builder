import argparse
from pathlib import Path
from .config import load_config
from .template import render_script

def main():
    parser = argparse.ArgumentParser(description="Generate NAS sync script")
    parser.add_argument("-c", "--config", type=Path, default=Path("nas_sync_config.yaml"))
    parser.add_argument("-o", "--output", type=Path, default=Path("nas-sync.sh"))
    args, unknown = parser.parse_known_args()

    if unknown:
        print(f"Ignored unknown argument(s): {unknown}")

    if args.config.exists():
        cfg = load_config(args.config)

        script = render_script(cfg)
        
        args.output.write_text(script + "\n")
        args.output.chmod(0o755)

        print(f"Script written to {args.output}")
    else:
        from .config import NasSyncConfig, save_config
        from .partitions import detect_partition_fstypes, get_partition_nas_paths

        cfg = NasSyncConfig.defaults()

        cfg.partition_fstypes = detect_partition_fstypes()
        cfg.partition_nas_paths = get_partition_nas_paths(cfg.partition_fstypes)

        save_config(cfg, args.config)

        print(f"Config written to {args.config}")
