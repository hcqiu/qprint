## Python environment

Run all commands from the Qprint root folder. This project uses only its local
Conda prefix `.conda`; do not use a named or global Python environment.

First-time user setup (in Anaconda Prompt / Miniconda Prompt):

```text
conda init powershell
conda env create -p .\.conda -f environment.yml
```

After setup, agents do not run `conda activate` or discover machine-specific
Python/Conda installation paths. Use the local interpreter directly:

```powershell
.\.conda\python.exe -m qprint agent state
.\.conda\python.exe -m qprint serve --workspace examples/demo
.\.conda\python.exe -m pip ...
.\.conda\python.exe -m pytest ...
```

`conda run -p .\.conda python ...` is an alternative when Conda is available.
Keep command arguments and user-facing file locations relative to the Qprint
folder. If `.conda` is missing, report the first-time setup command above;
do not fall back to another environment. Recreate `.conda` at a new installation
location rather than copying an existing Conda environment between machines.
