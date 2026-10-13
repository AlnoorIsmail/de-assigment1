"""Execute the complete assignment notebook from any working directory."""
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "assignment-matplotlib"))
os.environ.setdefault("IPYTHONDIR", str(Path(tempfile.gettempdir()) / "assignment-ipython"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "assignment-cache"))
notebook_path = ROOT / "marketplace_assignment.ipynb"
notebook = nbformat.read(notebook_path, as_version=4)
manager = KernelManager(kernel_name="python3")
manager.transport = "ipc"
manager.ip = str(Path(tempfile.gettempdir()) / f"assignment-kernel-{os.getpid()}")
manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
client = NotebookClient(notebook, km=manager, timeout=600, resources={"metadata": {"path": str(ROOT)}})
try:
    client.execute()
finally:
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)
nbformat.write(notebook, notebook_path)
print(f"Completed {notebook_path.name}. Outputs are in the configured output directory.")
