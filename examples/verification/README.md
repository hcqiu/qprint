# Managed verification example

This workspace exercises Lean 4.19.0 and Agda 2.8.0 with pinned Cubical 0.9. It has no network-dependent Lean libraries. Compiler installations belong to Qprint's ignored `toolchains/` store, not to this workspace.

From the Qprint root, install the catalog entries if necessary:

```powershell
conda run -n qprint python -m qprint toolchain install lean-4.19.0-windows-x64
conda run -n qprint python -m qprint toolchain install agda-2.8.0-windows-x64
conda run -n qprint python -m qprint toolchain install cubical-0.9
conda run -n qprint python -m qprint verify --workspace examples/verification
```

Full ZIPs already contain those environments. They still require the Python dependencies. Read the [Chinese](../../docs/toolchains.md) or [English](../../docs/toolchains.en.md) toolchain guide.
