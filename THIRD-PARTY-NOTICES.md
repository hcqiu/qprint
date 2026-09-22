# Third-party material in Qprint

The Qprint noncommercial and commercial licenses apply only to original material the relevant licensor has the right to license. They do not replace licenses granted by third parties or restrict those independently granted rights.

| Material | License / location |
| --- | --- |
| Vendored KaTeX JavaScript, CSS, and fonts | MIT; the original copyright and license text are retained at `qprint/static/vendor/katex/LICENSE`. Provenance is stored alongside the assets. |
| Agda license notice bundled with Qprint | Original notice retained at `qprint/toolchain-licenses/agda-2.8.0.txt`; this notice accompanies managed Agda installations. |
| Optional Lean / Agda compilers and Cubical libraries | Retain the upstream licenses and notices in their installed directories under `toolchains/` and `packages/`. Full Release ZIPs include these separately licensed components. |
| Python dependencies | Their respective upstream licenses apply. Requirements in `pyproject.toml` and `requirements-lock.txt` are dependency declarations, not a Qprint license grant for those packages. Installed distributions provide their own metadata and notices. |
| Imported repositories, papers, examples of external origin, and other user content | Their respective owners' terms and provenance apply, including licenses stored inside each repository. Downloading, importing, or verifying material does not relicense it as Qprint. |

This is a scope notice, not a claim that every third-party component uses the same license or that every distribution combination is permitted. Preserve upstream notices and satisfy each component's conditions when redistributing a bundle. A commercial agreement with Qprint's author cannot grant rights owned solely by another party. Where material lacks a license, do not infer permission from its availability.
