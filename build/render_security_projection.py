"""Render only MathCraft's four runtime credentials to an operator's private directory."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NAMES = ("ANTHROPIC_API_KEY", "MATHCRAFT_PARENT_PASSWORD", "MATHCRAFT_SESSION_KEY", "MATHCRAFT_DEVICE_KEY")


def render(output):
    source = next((parent / "tools/vault/vault_client.py" for parent in ROOT.parents
                   if (parent / "tools/vault/vault_client.py").is_file()), None)
    if source is None:
        raise RuntimeError("Central authenticated Vault client unavailable")
    spec = importlib.util.spec_from_file_location("mathcraft_projection_vault", source)
    client = importlib.util.module_from_spec(spec)
    previous = list(sys.path)
    try:
        sys.path.insert(0, str(source.parent))
        spec.loader.exec_module(client)
    finally:
        sys.path[:] = previous
    snapshot = client.ProjectVault().snapshot()
    values = {name: snapshot[name] for name in NAMES}
    path = Path(output).expanduser().absolute()
    if ROOT == path or ROOT in path.parents:
        raise RuntimeError("Runtime credentials must remain outside the project")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("Projection requires a private owned directory")
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise RuntimeError("Unsafe existing projection")
    fd, temporary = tempfile.mkstemp(prefix=".mathcraft-projection-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(values, stream)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    print("Four MathCraft credentials projected privately; values suppressed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        render(args.output)
    except Exception:
        print("MathCraft projection failed; no fallback or credential output.", file=sys.stderr)
        raise SystemExit(1)
