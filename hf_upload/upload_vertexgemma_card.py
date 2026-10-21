"""Actualiza la ficha de Denisijcu/vertexgemma: README, NOTICE y Modelfile.
No sube ni borra el GGUF. Correr desde E:\\vertex-chess-arena con el venv."""
from pathlib import Path
from huggingface_hub import upload_folder

here = Path(__file__).resolve().parent / "vertexgemma"
info = upload_folder(
    repo_id="Denisijcu/vertexgemma",
    folder_path=str(here),
    allow_patterns=["README.md", "NOTICE", "Modelfile.*"],
    commit_message="Model card: real training details (625 steps), evaluation, Gemma notice, Modelfile",
)
print("OK:", info)
