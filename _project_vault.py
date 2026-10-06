"""Read local credentials through the shared, authenticated Vault client."""
import importlib.util
import os
import sys
from pathlib import Path
_CLIENT = None

def get_secret(name, default=None, *, env_name=None):
    global _CLIENT
    if os.environ.get('PROJECT_VAULT_PROJECTED') == '1':
        projection_file = os.environ.get('PROJECT_VAULT_SECRETS_FILE')
        if projection_file:
            import json
            import stat
            source = Path(projection_file)
            metadata = source.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                raise RuntimeError('Unsafe consumer projection permissions')
            values = json.loads(source.read_text())
            if not isinstance(values, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in values.items()):
                raise RuntimeError('Invalid consumer projection schema')
            value = values.get(env_name or name, default)
        else:
            value = os.environ.get(env_name or name, default)
        if isinstance(value, str) and value.startswith('USE_VAULT'):
            raise RuntimeError('An unresolved Vault marker was projected')
        return value
    if _CLIENT is None:
        override = os.environ.get('VAULT_CLIENT_FILE')
        candidates = [Path(override)] if override else [p / 'tools/vault/vault_client.py' for p in Path(__file__).resolve().parents]
        source = next((p for p in candidates if p.is_file()), None)
        if source is None:
            raise RuntimeError('Central Vault client unavailable; use the Vault deployment launcher')
        spec = importlib.util.spec_from_file_location('_project_shared_vault', source)
        _CLIENT = importlib.util.module_from_spec(spec)
        previous_path = list(sys.path)
        try:
            sys.path.insert(0, str(source.parent))
            spec.loader.exec_module(_CLIENT)
        finally:
            sys.path[:] = previous_path
    return _CLIENT.get_secret(name, default)
