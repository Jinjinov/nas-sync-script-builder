# nas-sync-script-builder
Python GUI tool to generate bash scripts for one-way, no-deletion NAS sync using rsync and lsyncd.

Required by nas-sync-script-builder:
```
python3 -m venv venv
source venv/bin/activate
pip install PySide6
pip install Jinja2
pip install PyYAML
pip install pydbus
```

Required by PyGObject:
```
sudo apt install libgirepository-2.0-dev libcairo2-dev pkg-config
```

Required by pydbus:
```
pip install PyGObject
```