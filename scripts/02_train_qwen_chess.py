"""
VERTEX CHESS ARENA - Qwen 2.5 (3B) V3: entrenamiento ESPEJO del de Gemma 2 (2B).

Por qué existe esta versión (ver logs/bitacora.md, 2026-10-20):
  - El Qwen que estaba en Ollama era el adaptador viejo de 80 pasos, entrenado con el
    dataset de 3,000 filas y con pérdida sobre TODO el texto (system + FEN + lista de
    jugadas). Gemma se entrenó con 5,000 filas y pérdida solo sobre la respuesta.
  - Para que el duelo sea justo, este script copia la receta de 03_train_gemma_chess.py:
    mismo dataset, mismo Trainer + DataCollatorForSeq2Seq, misma máscara (-100) sobre el
    prompt, mismos hiperparámetros (r=8, alpha=16, lr=5e-5, warmup=15, cosine, 1 época,
    batch efectivo 8, fp16, seed 42, MAX_SEQ_LENGTH=384).
  - Lo único que cambia es el formato de chat: Qwen usa ChatML con rol system propio.

Correr desde E:\\vertex-chess-arena :
    venv\\Scripts\\python.exe scripts\\02_train_qwen_chess.py
"""
from __future__ import annotations

import os
import gc

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:32"
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import json
import random
from pathlib import Path
from typing import Any
from collections import Counter

BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache"
TMP_DIR = CACHE_DIR / "tmp"
HF_CACHE_DIR = CACHE_DIR / "huggingface"
TORCH_CACHE_DIR = CACHE_DIR / "torch"
TRITON_CACHE_DIR = CACHE_DIR / "triton"
for d in [TMP_DIR, HF_CACHE_DIR, TORCH_CACHE_DIR, TRITON_CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ["HF_DATASETS_CACHE"] = str(HF_CACHE_DIR / "datasets")
os.environ["TORCH_HOME"] = str(TORCH_CACHE_DIR)
os.environ["TRITON_CACHE_DIR"] = str(TRITON_CACHE_DIR)
os.environ["TMP"] = str(TMP_DIR)
os.environ["TEMP"] = str(TMP_DIR)

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model
from datasets import Dataset

# =============================================================================
# CONFIGURACIÓN — IDÉNTICA A 03_train_gemma_chess.py (salvo modelo y rutas)
# =============================================================================
BASE_MODEL = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
DATASET_PATH = BASE_DIR / "dataset" / "processed" / "train_chess_elite.jsonl"
OUTPUT_DIR = BASE_DIR / "outputs_qwen_v3"
FINAL_DIR = BASE_DIR / "models" / "qwen_chess_adapter_v3"

MAX_SEQ_LENGTH = 384
SEED = 42
NUM_EPOCHS = 1
MAX_STEPS = -1                 # 1 época completa = 5000 / 8 = 625 pasos, igual que Gemma
PER_DEVICE_BATCH_SIZE = 1
GRADIENT_ACCUMULATION_STEPS = 8
LEARNING_RATE = 5e-5
WARMUP_STEPS = 15

LORA_R = 8
LORA_ALPHA = 16
LORA_DROPOUT = 0.0
LORA_TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]

END_OF_TURN = "<|im_end|>"


def encode_example(messages: list[dict[str, str]], tok) -> tuple[list[int], list[int]]:
    """prompt (system+user+'<|im_start|>assistant\\n') enmascarado; se entrena solo
    la respuesta + <|im_end|>, exactamente como Gemma entrena respuesta + <end_of_turn>."""
    prompt_msgs = [m for m in messages if m["role"] != "assistant"]
    answer = next(m["content"] for m in messages if m["role"] == "assistant")

    prompt_text = tok.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
    prompt_ids = tok.encode(prompt_text, add_special_tokens=False)
    answer_ids = tok.encode(answer, add_special_tokens=False)
    eot_ids = tok.encode(END_OF_TURN, add_special_tokens=False)
    nl_ids = tok.encode("\n", add_special_tokens=False)

    ids = list(prompt_ids) + answer_ids + eot_ids + nl_ids
    labels = [-100] * len(prompt_ids) + answer_ids + eot_ids + [-100] * len(nl_ids)
    return ids, labels


def build_dataset(records: list[dict[str, Any]], tok) -> tuple[list[dict[str, Any]], Counter]:
    stats: Counter[str] = Counter()
    rows = []
    for rec in records:
        ids, labels = encode_example(rec["messages"], tok)
        if len(ids) > MAX_SEQ_LENGTH:
            stats["drop_too_long"] += 1
            continue
        if all(l == -100 for l in labels):
            stats["drop_no_labels"] += 1
            continue
        rows.append({"input_ids": ids, "attention_mask": [1] * len(ids), "labels": labels})
        stats["kept"] += 1
    return rows, stats


def main() -> None:
    random.seed(SEED)
    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    gc.collect()
    torch.cuda.empty_cache()

    print("=" * 65)
    print(f">>> QWEN 2.5 (3B) V3 — ESPEJO DE GEMMA | Dataset: {DATASET_PATH}")
    print("=" * 65)

    tok = AutoTokenizer.from_pretrained(BASE_MODEL, model_max_length=MAX_SEQ_LENGTH, cache_dir=str(HF_CACHE_DIR))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"

    records = [json.loads(l) for l in Path(DATASET_PATH).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows, stats = build_dataset(records, tok)
    print(f"Registros totales: {len(records)} | Conservados: {stats['kept']} | Descartados: {dict(stats)}")

    # Muestra de control: lo que ve el modelo y lo que aprende
    sample = rows[0]
    learned = [t for t, l in zip(sample["input_ids"], sample["labels"]) if l != -100]
    print(">>> Ejemplo de tokens entrenados:", repr(tok.decode(learned)))

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA es obligatorio en este entorno.")
    torch.cuda.empty_cache()
    gc.collect()

    print(">>> Cargando Qwen 2.5 3B (bnb-4bit) en torch.float16...")
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        attn_implementation="eager",
        device_map="auto",
        cache_dir=str(HF_CACHE_DIR),
    )
    model.config.use_cache = False

    model = get_peft_model(model, LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=LORA_TARGET_MODULES,
    ))
    model.print_trainable_parameters()
    model.enable_input_require_grads()

    random.shuffle(rows)
    train_ds = Dataset.from_list(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        max_steps=MAX_STEPS,
        per_device_train_batch_size=PER_DEVICE_BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        warmup_steps=WARMUP_STEPS,
        lr_scheduler_type="cosine",
        logging_steps=1,
        save_strategy="steps",
        save_steps=125,              # checkpoints por si se corta (Gemma usaba "no")
        save_total_limit=2,
        bf16=False,
        fp16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="adamw_torch",
        report_to="none",
        seed=SEED,
        data_seed=SEED,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8),
    )

    print(">>> Arrancando entrenamiento V3 (fp16, GTX 1660 Ti)...")
    last_ckpt = None
    ckpts = sorted(OUTPUT_DIR.glob("checkpoint-*"), key=lambda p: int(p.name.split("-")[1]))
    if ckpts:
        last_ckpt = str(ckpts[-1])
        print(f">>> Reanudando desde {last_ckpt}")
    trainer.train(resume_from_checkpoint=last_ckpt)

    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    trainer.model.save_pretrained(str(FINAL_DIR))
    tok.save_pretrained(str(FINAL_DIR))
    (FINAL_DIR / "train_log.json").write_text(json.dumps(trainer.state.log_history, indent=1), encoding="utf-8")
    print(f"\n>>> Qwen V3 entrenado. Adaptador en: {FINAL_DIR}")


if __name__ == "__main__":
    main()
