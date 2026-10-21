"""Actualiza la ficha de Denisijcu/vertexqwen: README, LICENSE de Qwen, NOTICE y Modelfiles.
No sube ni borra los GGUF. Correr desde E:\\vertex-chess-arena con el venv."""
from pathlib import Path
import shutil
from huggingface_hub import hf_hub_download, upload_folder

here = Path(__file__).resolve().parent / "vertexqwen"
lic = hf_hub_download("Qwen/Qwen2.5-3B-Instruct", "LICENSE")
shutil.copyfile(lic, here / "LICENSE")
info = upload_folder(
    repo_id="Denisijcu/vertexqwen",
    folder_path=str(here),
    allow_patterns=["README.md", "LICENSE", "NOTICE", "Modelfile.*"],
    commit_message="Model card: correct license (Qwen Research), real training details, evaluation, Modelfiles",
)
print("OK:", info)
