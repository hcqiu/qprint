"""Remove installation-specific filesystem locations from agent-facing values."""
from pathlib import Path
import re


def relative_output(value, base=None):
    base = Path(base or Path.cwd()).resolve()
    if isinstance(value, dict):
        return {k: relative_output(v, base) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [relative_output(v, base) for v in value]
    if isinstance(value, Path):
        value = str(value)
    if not isinstance(value, str):
        return value
    # Preserve usable paths inside this installation, including spaces.
    for root in {str(base), base.as_posix()}:
        value = re.sub(re.escape(root) + r'(?=$|[/\\\s\x27\x22)])', '.', value, flags=re.IGNORECASE)
    # External interpreter/cache paths in OS diagnostics are not agent paths.
    value = re.sub(r'(?<![\w])[A-Za-z]:[/\\][^\s\x22\x27<>]*', '[external-path]', value)
    value = re.sub(r'(?<![\w:/])/(?:Users|home|tmp|private|var|opt|etc|mnt|usr|root)(?:/[^\s\x22\x27<>]*)?', '[external-path]', value)
    return value
