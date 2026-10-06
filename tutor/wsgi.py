"""Production WSGI entry point; configuration and credentials are projected by systemd."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tutor"))
from server import build_app

app = build_app()
