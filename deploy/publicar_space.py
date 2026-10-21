"""
Publica el backend de Vertex Chess Arena en un Space de Hugging Face con ZeroGPU.

  1. Sube los adaptadores LoRA a los repos de modelos (ZeroGPU usa PyTorch, no GGUF):
       Denisijcu/vertexqwen  -> adapter-v3/  y  adapter-legacy/
       Denisijcu/vertexgemma -> adapter/
     y las fichas actualizadas de hf_upload/.
  2. Crea (o actualiza) el Space Denisijcu/vertex-chess-arena con deploy/space/ + arena/engine_arbiter.py
     y le pide hardware ZeroGPU.

Uso, desde E:\\vertex-chess-arena:
  venv\\Scripts\\python.exe deploy\\publicar_space.py                 (todo)
  venv\\Scripts\\python.exe deploy\\publicar_space.py --solo-space    (solo el código del Space)
  venv\\Scripts\\python.exe deploy\\publicar_space.py --app-url https://xxx.netlify.app   (además, enlace a la app)
"""
import argparse
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
SPACE = "Denisijcu/vertex-chess-arena"
ADAPTERS = [
    ("Denisijcu/vertexqwen", ROOT / "models" / "qwen_chess_adapter_v3", "adapter-v3"),
    ("Denisijcu/vertexqwen", ROOT / "models" / "qwen_chess_adapter", "adapter-legacy"),
    ("Denisijcu/vertexgemma", ROOT / "models" / "gemma_chess_adapter", "adapter"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--solo-space", action="store_true")
ap.add_argument("--app-url", default="")
args = ap.parse_args()

api = HfApi()
print("Cuenta de Hugging Face:", api.whoami()["name"])

if not args.solo_space:
    for repo, src, sub in ADAPTERS:
        for f in ("adapter_config.json", "adapter_model.safetensors"):
            if not (src / f).exists():
                raise SystemExit(f"Falta {src / f}")
        api.upload_folder(repo_id=repo, folder_path=str(src), path_in_repo=sub,
                          allow_patterns=["adapter_config.json", "adapter_model.safetensors"],
                          commit_message=f"LoRA adapter ({sub}) for the ZeroGPU Space")
        print(f"OK adaptador {src.name} -> {repo}/{sub}")
    for repo, folder in (("Denisijcu/vertexqwen", "vertexqwen"), ("Denisijcu/vertexgemma", "vertexgemma")):
        api.upload_folder(repo_id=repo, folder_path=str(ROOT / "hf_upload" / folder), allow_patterns=["README.md"],
                          commit_message="Model card: LoRA adapters and the playable Space")
        print("OK ficha", repo)

api.create_repo(SPACE, repo_type="space", space_sdk="gradio", exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    for f in (ROOT / "deploy" / "space").iterdir():
        if f.is_file():
            shutil.copy(f, tmp)
    shutil.copy(ROOT / "arena" / "engine_arbiter.py", tmp)  # el mismo árbitro que la arena local
    api.upload_folder(repo_id=SPACE, repo_type="space", folder_path=tmp,
                      commit_message="Vertex Chess Arena API (ZeroGPU)")
print("OK código del Space")

if args.app_url:
    api.add_space_variable(SPACE, "APP_URL", args.app_url)
    print("OK variable APP_URL =", args.app_url)

try:
    api.request_space_hardware(SPACE, "zero-a10g")
    print("OK hardware ZeroGPU solicitado")
except Exception as e:  # noqa: BLE001
    print("No se pudo pedir ZeroGPU desde aquí:", e)
    print("Hazlo a mano: Space > Settings > Space hardware > ZeroGPU")

print(f"\nListo: https://huggingface.co/spaces/{SPACE}  (la primera vez tarda unos minutos en construir)")
