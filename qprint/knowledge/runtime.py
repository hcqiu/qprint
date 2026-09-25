"""Portable UI-to-agent rendezvous, relative to the opened Qprint folder."""
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile

from ..paths import WorkspaceError, safe_path


def relative_workspace(base, value):
    value = str(value).replace('\\', '/')
    if Path(value).is_absolute() or PureWindowsPath(value).drive:
        raise WorkspaceError('workspace must be relative to the Qprint folder')
    if value in {'.', './'}:
        return Path(base).resolve()
    try:
        return safe_path(Path(base), value.rstrip('/'))
    except WorkspaceError:
        raise WorkspaceError('workspace must stay inside the Qprint folder') from None


def active_runtime(base):
    path = safe_path(Path(base), '.qprint/runtime/navigation.json')
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError()
        relative_workspace(base, data['workspace'])
        if not isinstance(data['session'], str) or not 1 <= len(data['session']) <= 200:
            raise ValueError()
        return data
    except (ValueError, KeyError, TypeError):
        raise WorkspaceError('Invalid Qprint runtime state; reopen the Qprint UI') from None


def publish_runtime(base, workspace, session):
    base, workspace = Path(base).resolve(), Path(workspace).resolve()
    if not workspace.is_relative_to(base):
        raise WorkspaceError('workspace must stay inside the Qprint folder')
    path = safe_path(base, '.qprint/runtime/navigation.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'version': 1, 'workspace': workspace.relative_to(base).as_posix(), 'session': session}
    # Readers observe either complete old or complete new state, never partial JSON.
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='navigation-', suffix='.tmp')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=True)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def query_target(base, workspace=None, session=None):
    active = active_runtime(base)
    root = relative_workspace(base, workspace if workspace is not None else active['workspace'] if active else '.')
    follows_active = active and root == relative_workspace(base, active['workspace'])
    return root, session if session is not None else active['session'] if follows_active else 'default'
