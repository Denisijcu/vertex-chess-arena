---
language:
- en
license: gemma
base_model: google/gemma-2-2b-it
tags:
- chess
- qlora
- gguf
- ollama
- gemma2
- vertex-coders
---

# Vertex-Gemma Chess (Gemma 2 2B, QLoRA, GGUF)

A small research experiment by **Vertex Coders LLC** (Denis Sanchez Leyva, Miami, FL):
Gemma 2 2B IT fine-tuned with QLoRA to pick a chess move from a list of legal moves and
answer in a fixed format. It was trained to be compared head-to-head against
[Denisijcu/vertexqwen](https://huggingface.co/Denisijcu/vertexqwen) (Qwen 2.5 3B) with the
same data and the same recipe, in the **Vertex Chess Arena** project and the book
*Jaque al modelo*.

> This is **not** a strong chess engine. It learned the answer **format** very well and picks
> the reference move more often than the Qwen model, but it does not play well on its own.
> See *Evaluation*.

**Links:** code: [Denisijcu/vertex-chess-arena](https://github.com/Denisijcu/vertex-chess-arena) ·
sister model: [Denisijcu/vertexqwen](https://huggingface.co/Denisijcu/vertexqwen) ·
video: [YouTube](https://youtu.be/2_t0ijTg1_M) ·
play it: [Space](https://huggingface.co/spaces/Denisijcu/vertex-chess-arena) ·
book: *Jaque al modelo* (Spanish, coming soon on Amazon)

## Files

| File | What it is |
|---|---|
| `vertex-chess-gemma-q4_k_m.gguf` | Base + LoRA merged, quantized to `q4_k_m` (1.7 GB) |
| `Modelfile.gemma` | Ollama Modelfile with explicit Gemma template and stop tokens |
| `adapter/` | The LoRA adapter (PEFT) for `google/gemma-2-2b-it`, used by the playable Space |

## Prompt format

Gemma 2 has no system role. In training and in the arena, the system text goes **at the
start of the user message**, followed by a blank line:

```
You are an elite chess grandmaster engine created by Vertex Coders. Analyze the FEN board state and the list of legal moves, then output the single strongest tactical move in both SAN and UCI formats.

Position FEN: <fen>
Legal moves (SAN): <comma-separated legal moves>
Select the best move.
```

Expected answer:

```
Best move: Nf3 (UCI: g1f3)
```

The included Modelfile also accepts a separate `system` message and merges it the same way.

## Training

- Data: 5,000 positions (40% Lichess engine evaluations, 40% Lichess puzzles, 20% `agi-noobs/chess-sft-20k`), validated with python-chess.
- QLoRA with `transformers` + `peft` + `bitsandbytes` on `unsloth/gemma-2-2b-it-bnb-4bit`: r=8, alpha=16, dropout 0, all attention and MLP projections.
- lr 5e-5, 15 warmup steps, cosine, effective batch 8 (1×8), max length 384, fp16, eager attention, `adamw_torch`, seed 42.
- Loss on the answer only (prompt masked with -100).
- 625 steps (1 epoch) on an NVIDIA GTX 1660 Ti 6 GB: about 11 hours.
- Exported with Unsloth to GGUF `q4_k_m`.

## Evaluation

40 positions **from the training set** (format = answers `Best move:`; match = same move as the dataset):

| Model | Format | Match |
|---|---|---|
| **Gemma 2 2B (this model)** | **40/40** | **9/40** |
| Qwen 2.5 3B V3 (same recipe) | 39/40 | 4/40 |

10-game match, model choosing among **all** legal moves: Gemma 5.5 – Qwen V3 4.5 (9 draws by threefold repetition). Valid answers: Gemma 99.2%, Qwen 95.5%.
In a 7-player round robin, every model **with** a move-filtering arbiter beat every model **without** it (9–0): with the filter, the differences between models disappear.

## Use with Ollama

Download the files (about 1.7 GB), then register the model:

```powershell
pip install -U huggingface_hub
hf download Denisijcu/vertexgemma vertex-chess-gemma-q4_k_m.gguf Modelfile.gemma --local-dir vertexgemma
cd vertexgemma
ollama create vertexgemma -f Modelfile.gemma
ollama run vertexgemma
```

Send the prompt exactly as in *Prompt format*, with the full list of legal moves. It was
trained on this format only.

## Limitations

- Trained on 5,000 positions, one epoch: enough to learn the answer format, not to play well.
- Evaluated only on positions from the training set; no held-out benchmark yet.
- Without a move filter, games tend to end in threefold repetition.
- The model only picks from the moves it is given. It does not check legality by itself: use `python-chess` or similar.

## License

Gemma is provided under and subject to the **Gemma Terms of Use** found at
[ai.google.dev/gemma/terms](https://ai.google.dev/gemma/terms). This model is a Model
Derivative of google/gemma-2-2b-it; its use is subject to those terms and to the
[Gemma Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy). See `NOTICE`.
