"""Private one-shot rendering process with a parent-enforced time limit."""
import json
import sys

from .tex import _render_tex_dom


if __name__ == "__main__":
    request = json.load(sys.stdin)
    result = _render_tex_dom(request["fragment"], request["preamble"], request.get("references"),
                             labels=request.get("labels"), index_only=request.get("index_only", False))
    print(json.dumps(result))
