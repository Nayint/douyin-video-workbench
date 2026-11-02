import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.backup import restore_backup
if len(sys.argv)!=2:raise SystemExit('用法：.venv/bin/python scripts/restore.py backups/备份.zip')
print('恢复完成；恢复前快照：'+restore_backup(sys.argv[1]))
