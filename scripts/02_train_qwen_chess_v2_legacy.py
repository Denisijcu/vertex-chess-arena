"""
VERTEX CHESS ARENA - Entrenamiento QLoRA V2 para Qwen 2.5 (3B)
Optimizado para el Grandmaster Blend (5,000 posiciones auditadas).
"""
import os
import gc
from pathlib import Path

BASE_DIR = Path("E:/vertex-chess-arena").resolve()
CACHE_DIR = BASE_DIR / ".cache"
os.environ["HF_HOME"] = str(CACHE_DIR / "huggingface")
os.environ["TORCH_HOME"] = str(CACHE_DIR / "torch")
os.environ["TMP"] = str(CACHE_DIR / "tmp")
os.environ["TEMP"] = str(CACHE_DIR / "tmp")
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:128"
os.environ["UNSLOTH_COMPILE_DISABLE"] = "1"

import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

MODEL_NAME = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
DATASET_PATH = BASE_DIR / "dataset" / "processed" / "train_chess_elite.jsonl"
OUTPUT_ADAPTER = BASE_DIR / "models" / "adapters" / "qwen_chess_lora"

# 384 cubre comodamente los ~273 tokens reales (FEN + Chat Template) sin disparar el bug de truncado de Unsloth
MAX_SEQ_LENGTH = 384
MAX_STEPS = 250


def train_qwen():
    print("=" * 70)
    print(">>> [VERTEX TRAIN V2] INICIANDO FINE-TUNING DE QWEN 2.5 (3B) - GRANDMASTER BLEND")
    print("=" * 70)

    gc.collect()
    torch.cuda.empty_cache()

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=torch.float16,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha=32,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset = load_dataset("json", data_files=str(DATASET_PATH), split="train")

    def format_chat(examples):
        texts = [
            tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            for msgs in examples["messages"]
        ]
        return {"text": texts}

    dataset = dataset.map(format_chat, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=1,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            warmup_steps=15,
            max_steps=MAX_STEPS,
            learning_rate=1.5e-4,
            fp16=True,
            bf16=False,
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            seed=42,
            output_dir=str(BASE_DIR / "models" / "checkpoints_qwen"),
            report_to="none",
            dataloader_num_workers=0,
        ),
    )

    trainer.train()

    OUTPUT_ADAPTER.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(OUTPUT_ADAPTER))
    tokenizer.save_pretrained(str(OUTPUT_ADAPTER))
    print(f"\n>>> [OK] Adaptador Qwen V2 guardado en: {OUTPUT_ADAPTER}")


if __name__ == "__main__":
    train_qwen()