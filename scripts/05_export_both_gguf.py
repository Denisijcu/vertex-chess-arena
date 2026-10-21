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

QWEN_TEMPLATE = """{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""

GEMMA_TEMPLATE = """{{- $system := "" }}
{{- range .Messages }}
{{- if eq .Role "system" }}{{ $system = .Content }}{{ continue }}
{{- else if eq .Role "user" }}<start_of_turn>user
{{- if $system }}
{{ $system }}

{{- $system = "" }}
{{- end }}
{{- else if eq .Role "assistant" }}<start_of_turn>model
{{- end }}
{{ .Content }}<end_of_turn>
{{ end }}<start_of_turn>model
"""


def _modelfile(gguf_name: str, template: str, stops: list[str]) -> str:
    """V3: TEMPLATE y stops explícitos. Antes los Modelfiles solo tenían FROM y Ollama tenía
    que adivinar la plantilla a partir del GGUF."""
    lines = [f"FROM ./{gguf_name}", f'TEMPLATE """{template}"""']
    lines += [f'PARAMETER stop "{s}"' for s in stops]
    lines += ["PARAMETER temperature 0.1", "PARAMETER repeat_penalty 1.15", "PARAMETER num_ctx 1024"]
    return "\n".join(lines) + "\n"


def write_clean_modelfiles() -> None:
    """Modelfiles UTF-8 sin BOM (evita el 400 Bad Request de Ollama)."""
    files = {
        "Modelfile.qwen-v3": _modelfile("vertex-chess-qwen-v3-q4_k_m.gguf", QWEN_TEMPLATE, ["<|im_end|>", "<|endoftext|>"]),
        "Modelfile.gemma": _modelfile("vertex-chess-gemma-q4_k_m.gguf", GEMMA_TEMPLATE, ["<end_of_turn>", "<start_of_turn>"]),
    }
    for name, content in files.items():
        with open(GGUF_DIR / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    print("\n>>> Modelfiles generados. Para registrar en Ollama (desde E:\\vertex-chess-arena\\models\\gguf):")
    print("    ollama create vertexqwen-v3 -f Modelfile.qwen-v3")
    print("    (vertexgemma ya está registrado; Modelfile.gemma queda como referencia)")


if __name__ == "__main__":
    # V3: solo se exporta el Qwen nuevo. El GGUF de Gemma ya existe y no se toca, para que
    # el Gemma del duelo sea exactamente el mismo que ya jugó.
    if not (GGUF_DIR / "vertex-chess-qwen-v3-q4_k_m.gguf").exists():
        export_contender("qwen_chess_adapter_v3", "vertex-chess-qwen-v3-q4_k_m.gguf")
    if not (GGUF_DIR / "vertex-chess-gemma-q4_k_m.gguf").exists():
        export_contender("gemma_chess_adapter", "vertex-chess-gemma-q4_k_m.gguf")
    write_clean_modelfiles()
