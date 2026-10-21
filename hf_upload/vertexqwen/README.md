---
language:
- en
license: other
license_name: qwen-research
license_link: LICENSE
base_model: Qwen/Qwen2.5-3B-Instruct
tags:
- chess
- qlora
- gguf
- ollama
- qwen2.5
- vertex-coders
---

# Vertex-Qwen Chess (Qwen 2.5 3B, QLoRA, GGUF)

**Built with Qwen.** A small research experiment by **Vertex Coders LLC** (Denis Sanchez Leyva, Miami, FL):
Qwen 2.5 3B Instruct fine-tuned with QLoRA to pick a chess move from a list of legal moves and
answer in a fixed format. It was trained to be compared head-to-head against Gemma 2 2B
fine-tuned on the same data, in the **Vertex Chess Arena** project and the book
*Jaque al modelo*.

> This is **not** a strong chess engine. It learned the answer **format** well; it does not
> play well on its own. See *Evaluation*.

**Links:** code: [Denisijcu/vertex-chess-arena](https://github.com/Denisijcu/vertex-chess-arena) ·
sister model: [Denisijcu/vertexgemma](https://huggingface.co/Denisijcu/vertexgemma) ·
video: [YouTube](https://youtu.be/2_t0ijTg1_M) ·
play it: [Space](https://huggingface.co/spaces/Denisijcu/vertex-chess-arena) ·
book: *Jaque al modelo* (Spanish, coming soon on Amazon)

## Files

| File | What it is |
|---|---|
| `vertex-chess-qwen-v3-q4_k_m.gguf` | **V3 (recommended).** 625 steps = 1 epoch, same recipe as the Gemma model |
| `vertex-chess-qwen-q4_k_m.gguf` | **Legacy**, kept for reproducibility. Early 80-step adapter, loss over the full text. Almost never answers in the expected format |
| `Modelfile.qwen-v3` | Ollama Modelfile with explicit ChatML template and stop tokens |
| `Modelfile.qwen-legacy` | The original legacy Modelfile, unchanged (no explicit template), as it was used in the experiment |
| `adapter-v3/`, `adapter-legacy/` | The LoRA adapters (PEFT) for `Qwen/Qwen2.5-3B-Instruct`, used by the playable Space |

## Prompt format

System message (exactly as in training):

```
You are an elite chess grandmaster engine created by Vertex Coders. Analyze the FEN board state and the list of legal moves, then output the single strongest tactical move in both SAN and UCI formats.
```

User message:

```
Position FEN: <fen>
Legal moves (SAN): <comma-separated legal moves>
Select the best move.
```

Expected answer:

```
Best move: Nf3 (UCI: g1f3)
```

## Training (V3)

- Data: 5,000 positions (40% Lichess engine evaluations, 40% Lichess puzzles, 20% `agi-noobs/chess-sft-20k`), validated with python-chess.
- QLoRA on `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`: r=8, alpha=16, dropout 0, all attention and MLP projections.
- lr 5e-5, 15 warmup steps, cosine, effective batch 8 (1×8), max length 384, fp16, eager attention, seed 42.
- Loss on the answer only (prompt masked with -100), including `<|im_end|>`.
- 625 steps (1 epoch) on an NVIDIA GTX 1660 Ti 6 GB: 13 h 42 min. Loss 4.23 → 0.23 (mean 0.36).
- Exported with Unsloth to GGUF `q4_k_m`.

## Evaluation

40 positions **from the training set** (format = answers `Best move:`; match = same move as the dataset):

| Model | Format | Match |
|---|---|---|
| Qwen V3 | 39/40 | 4/40 |
| Gemma 2 2B (same recipe) | 40/40 | 9/40 |
| Qwen legacy | 0/40 | 0/40 |

10-game match, model choosing among **all** legal moves: Gemma 5.5 – Qwen V3 4.5 (9 draws by threefold repetition).
In a 7-player round robin, every model **with** a move-filtering arbiter beat every model **without** it (9–0), and the legacy model scored the same as V3 while choosing 1 of 193 moves itself: the filter, not the model, was winning games.

## Use with Ollama

Download only the files you need (about 1.9 GB), then register the model:

```powershell
pip install -U huggingface_hub
hf download Denisijcu/vertexqwen vertex-chess-qwen-v3-q4_k_m.gguf Modelfile.qwen-v3 --local-dir vertexqwen
cd vertexqwen
ollama create vertexqwen-v3 -f Modelfile.qwen-v3
ollama run vertexqwen-v3
```

Always send the system message and the user message exactly as in *Prompt format*, with the
full list of legal moves. It was trained on this format only.

## Limitations

- Trained on 5,000 positions, one epoch: enough to learn the answer format, not to play well.
- Evaluated only on positions from the training set; no held-out benchmark yet.
- Without a move filter, games between these models tend to end in threefold repetition.
- Sometimes the SAN is right and the UCI part does not match the position (e.g. `Best move: Bb7 (UCI: d8b7)`). Parse the SAN first.
- The model only picks from the moves it is given. It does not check legality by itself: use `python-chess` or similar.

## License

Derivative of Qwen/Qwen2.5-3B-Instruct, distributed under the **Qwen RESEARCH LICENSE AGREEMENT** (see `LICENSE` and `NOTICE`). **Non-commercial use only** (research or evaluation). Commercial use requires a license from Alibaba Cloud.
