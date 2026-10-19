import os
import gc
import shutil
from pathlib import Path

# =====================================================================
# 0. AISLAMIENTO ESTRICTO EN LA UNIDAD E: + FIX DE DESCARGA HF XET
# =====================================================================
BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache"
HF_CACHE_DIR = CACHE_DIR / "huggingface"
TORCH_CACHE_DIR = CACHE_DIR / "torch"
TRITON_CACHE_DIR = CACHE_DIR / "triton"
TMP_DIR = CACHE_DIR / "tmp"

for d in [HF_CACHE_DIR, TORCH_CACHE_DIR, TRITON_CACHE_DIR, TMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(HF_CACHE_DIR / "datasets")
os.environ["TORCH_HOME"] = str(TORCH_CACHE_DIR)
os.environ["TRITON_CACHE_DIR"] = str(TRITON_CACHE_DIR)
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import torch
from unsloth import FastLanguageModel

GGUF_DIR = BASE_DIR / "models" / "gguf"
GGUF_DIR.mkdir(parents=True, exist_ok=True)

def export_contender(adapter_name: str, target_gguf_name: str) -> None:
    adapter_path = BASE_DIR / "models" / adapter_name
    if not (adapter_path / "adapter_config.json").exists():
        print(f">>> [OMITIDO] No se encontró {adapter_path / 'adapter_config.json'}")
        return

    gc.collect()
    torch.cuda.empty_cache()

    temp_export_dir = BASE_DIR / "models" / f"tmp_{adapter_name}"

    print(f"\n{'='*65}")
    print(f">>> EXPORTANDO {adapter_name} A GGUF (q4_k_m)...")
    print(f"{'='*65}")

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(adapter_path),
        max_seq_length=512,
        dtype=torch.float16,
        load_in_4bit=True,
        cache_dir=str(HF_CACHE_DIR),
    )

    model.save_pretrained_gguf(
        str(temp_export_dir),
        tokenizer,
        quantization_method="q4_k_m",
    )

    found_ggufs = list(temp_export_dir.rglob("*.gguf"))
    if not found_ggufs and Path(f"{temp_export_dir}_gguf").exists():
        found_ggufs = list(Path(f"{temp_export_dir}_gguf").rglob("*.gguf"))

    if found_ggufs:
        final_gguf_path = GGUF_DIR / target_gguf_name
        shutil.move(str(found_ggufs[0]), str(final_gguf_path))
        print(f">>> [OK] Binario GGUF listo en: {final_gguf_path}")
    else:
        print(f">>> [ADVERTENCIA] Revisa la carpeta {temp_export_dir} para localizar el archivo .gguf")

    del model
    del tokenizer
    gc.collect()
    torch.cuda.empty_cache()

def write_clean_modelfiles() -> None:
    """Crea Modelfiles en UTF-8 puro (sin BOM) para evitar el error 400 Bad Request en Ollama."""
    qwen_modelfile = GGUF_DIR / "Modelfile.qwen"
    gemma_modelfile = GGUF_DIR / "Modelfile.gemma"

    qwen_content = (
        "FROM ./vertex-chess-qwen-q4_k_m.gguf\n"
        "PARAMETER temperature 0.1\n"
        "PARAMETER repeat_penalty 1.15\n"
        "PARAMETER num_ctx 512\n"
    )
    gemma_content = (
        "FROM ./vertex-chess-gemma-q4_k_m.gguf\n"
        "PARAMETER temperature 0.1\n"
        "PARAMETER repeat_penalty 1.15\n"
        "PARAMETER num_ctx 512\n"
    )

    with open(qwen_modelfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(qwen_content)

    with open(gemma_modelfile, "w", encoding="utf-8", newline="\n") as f:
        f.write(gemma_content)

    print("\n>>> Modelfiles limpios (UTF-8 sin BOM) generados con éxito.")
    print(">>> Para registrar ambos modelos en Ollama ejecuta:")
    print("    cd E:\\vertex-chess-arena\\models\\gguf")
    print("    ollama create vertexqwen -f Modelfile.qwen")
    print("    ollama create vertexgemma -f Modelfile.gemma")

if __name__ == "__main__":
    export_contender("qwen_chess_adapter", "vertex-chess-qwen-q4_k_m.gguf")
    export_contender("gemma_chess_adapter", "vertex-chess-gemma-q4_k_m.gguf")
    write_clean_modelfiles()