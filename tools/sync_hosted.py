"""Bundle the read-only core into Vercel's frontend project root. Run after core edits."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
files = ['__init__.py', 'config.py', 'models.py', 'analytics.py', 'detector.py',
         'orderbook.py', 'graph.py', 'risk.py', 'news.py', 'india.py',
         'providers/__init__.py', 'providers/base.py', 'providers/mock.py', 'providers/live.py']
for name in files:
    target = root / 'frontend/hosted_core' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / 'backend/app' / name, target)
