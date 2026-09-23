"""Self-contained entry point: no Qprint checkout or installed package needed."""
from qprint_blueprint.tex_to_blueprint import main

if __name__ == "__main__":
    raise SystemExit(main())
