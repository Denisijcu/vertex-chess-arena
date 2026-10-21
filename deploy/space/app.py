"""
Vertex Chess Arena — backend en un Space de Hugging Face con ZeroGPU.

Sirve las jugadas de los modelos afinados del libro "Jaque al modelo" a la app Angular
publicada en Netlify. Mismo árbitro que la arena local (engine_arbiter.py); lo único que
cambia es quién genera el texto: aquí transformers + peft en la GPU de ZeroGPU, en casa Ollama.

Si la GPU no está disponible para un visitante (su cuota diaria de ZeroGPU se agotó), la jugada se
genera en CPU con los mismos GGUF q4_k_m del libro (llama.cpp): más lenta, pero sin cuota.

Endpoints (Gradio API, se llaman con @gradio/client):
  /health    -> estado y modelos cargados (sin GPU)
  /players   -> lista de jugadores (sin GPU)
  /ai_move   -> jugada de un modelo o del motor para un FEN (GPU solo si juega un modelo)
"""
import os
import threading
import time
from collections import OrderedDict

import chess
import gradio as gr
import spaces
import torch
from peft import PeftModel
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

from engine_arbiter import ChessArbiter

HF_TOKEN = os.getenv("HF_TOKEN")  # opcional
QWEN_BASE = "Qwen/Qwen2.5-3B-Instruct"
# Copia sin acceso restringido de google/gemma-2-2b-it (mismos pesos, licencia Gemma). Los adaptadores
# se entrenaron sobre las versiones de 4 bits de Unsloth de estos mismos modelos.
GEMMA_BASE = "unsloth/gemma-2-2b-it"
QWEN_REPO = "Denisijcu/vertexqwen"
GEMMA_REPO = "Denisijcu/vertexgemma"
ENGINE_ID = "vertex-engine"
APP_URL = os.getenv("APP_URL", "")

ROSTER = [
    {"model": "vertexqwen-v3", "name": "Qwen 2.5 · 3B · V3", "family": "qwen",
     "description": "Entrenamiento espejo de Gemma: 5,000 posiciones, pérdida solo en la respuesta, 625 pasos."},
    {"model": "vertexgemma", "name": "Gemma 2 · 2B", "family": "gemma",
     "description": "QLoRA r=8 sobre 5,000 posiciones, 625 pasos."},
    {"model": "vertexqwen", "name": "Qwen 2.5 · 3B · legacy", "family": "qwen",
     "description": "Adaptador viejo de 80 pasos. Se conserva para comparar."},
]
ROSTER_IDS = {p["model"] for p in ROSTER}

# ---------------------------------------------------------------------------
# Modelos: se cargan en "cuda" al arrancar (ZeroGPU lo emula fuera de @spaces.GPU)
# ---------------------------------------------------------------------------
qwen_tok = AutoTokenizer.from_pretrained(QWEN_BASE)
qwen = AutoModelForCausalLM.from_pretrained(QWEN_BASE, torch_dtype=torch.bfloat16)
# torch_device="cpu": PEFT cargaría los pesos directamente en "cuda" y en ZeroGPU no hay GPU real
# fuera de @spaces.GPU (RuntimeError: No CUDA GPUs are available). Se pasa todo a cuda después.
qwen = PeftModel.from_pretrained(qwen, QWEN_REPO, subfolder="adapter-v3", adapter_name="v3", torch_device="cpu")
qwen.load_adapter(QWEN_REPO, adapter_name="legacy", subfolder="adapter-legacy", torch_device="cpu")
qwen.to("cuda").eval()

gemma_tok = AutoTokenizer.from_pretrained(GEMMA_BASE, token=HF_TOKEN)
gemma = AutoModelForCausalLM.from_pretrained(GEMMA_BASE, torch_dtype=torch.bfloat16,
                                             attn_implementation="eager", token=HF_TOKEN)
gemma = PeftModel.from_pretrained(gemma, GEMMA_REPO, subfolder="adapter", torch_device="cpu")
gemma.to("cuda").eval()

_GEN_LOCK = threading.Lock()  # el adaptador activo de Qwen es estado global del modelo


@spaces.GPU(duration=10)  # una jugada tarda 1-3 s; pedir menos = menos cuota reservada y mejor prioridad
def generate(model_name: str, messages: list[dict]) -> str:
    """Respuesta del modelo con los mismos límites que en Ollama (48 tokens, casi determinista)."""
    if model_name == "vertexgemma":
        tok, model = gemma_tok, gemma
    else:
        tok, model = qwen_tok, qwen
    with _GEN_LOCK:
        if model is qwen:
            model.set_adapter("v3" if model_name == "vertexqwen-v3" else "legacy")
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt", add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=48, do_sample=False, repetition_penalty=1.15,
                                 pad_token_id=tok.eos_token_id)
    return tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)


# ---------------------------------------------------------------------------
# Respaldo en CPU: los mismos GGUF q4_k_m del libro con llama.cpp. Se usa cuando la GPU no está
# disponible para el visitante (cuota diaria de ZeroGPU agotada, cola llena...). Más lento, sin cuota.
# ---------------------------------------------------------------------------
GGUF = {
    "vertexqwen-v3": (QWEN_REPO, "vertex-chess-qwen-v3-q4_k_m.gguf", "chatml"),
    "vertexqwen": (QWEN_REPO, "vertex-chess-qwen-q4_k_m.gguf", "chatml"),
    "vertexgemma": (GEMMA_REPO, "vertex-chess-gemma-q4_k_m.gguf", "gemma"),
}
STOPS = {"chatml": ["<|im_end|>", "<|endoftext|>"], "gemma": ["<end_of_turn>", "<start_of_turn>"]}
_CPU: dict = {}
_CPU_LOCK = threading.Lock()


def render_prompt(fmt: str, messages: list[dict]) -> str:
    """La misma plantilla que los Modelfiles de Ollama (deploy de ajedrez, capítulo 6)."""
    if fmt == "gemma":  # Gemma no tiene rol de sistema: build_messages ya lo puso dentro del usuario
        turns = "".join(f"<start_of_turn>{'model' if m['role'] == 'assistant' else 'user'}\n{m['content']}<end_of_turn>\n"
                        for m in messages)
        return turns + "<start_of_turn>model\n"
    return "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages) + "<|im_start|>assistant\n"


def cpu_model(model_name: str):
    from llama_cpp import Llama  # import tardío: solo hace falta si se usa el respaldo
    with _CPU_LOCK:
        if model_name not in _CPU:
            repo, fname, _ = GGUF[model_name]
            path = hf_hub_download(repo, fname)
            _CPU[model_name] = Llama(model_path=path, n_ctx=1024, n_threads=max(2, os.cpu_count() or 2),
                                     verbose=False)
        return _CPU[model_name]


def generate_cpu(model_name: str, messages: list[dict]) -> str:
    fmt = GGUF[model_name][2]
    llm = cpu_model(model_name)
    with _CPU_LOCK:
        out = llm(render_prompt(fmt, messages), max_tokens=48, temperature=0.0, repeat_penalty=1.15,
                  stop=STOPS[fmt])
    return out["choices"][0]["text"]


def _warm_cpu():
    """Descarga y abre los GGUF en segundo plano al arrancar, para que el respaldo no espere."""
    for name in GGUF:
        try:
            cpu_model(name)
        except Exception as e:  # noqa: BLE001
            print("Respaldo CPU no disponible para", name, "->", e)


threading.Thread(target=_warm_cpu, daemon=True).start()

FORCE_CPU = os.getenv("FORCE_CPU") == "1"


def chat(model_name: str, messages: list[dict]) -> str:
    """GPU si se puede; si ZeroGPU la niega (cuota del visitante, cola), los GGUF en CPU."""
    if not FORCE_CPU:
        try:
            text = generate(model_name, messages)
            _LAST_DEVICE.value = "gpu"
            return text
        except Exception as e:  # noqa: BLE001
            print(f"GPU no disponible para {model_name}: {str(e)[:200]} -> respaldo CPU")
    _LAST_DEVICE.value = "cpu"
    return generate_cpu(model_name, messages)


_LAST_DEVICE = threading.local()


# ---------------------------------------------------------------------------
# Un árbitro por partida (guarda historial para el anti-repetición)
# ---------------------------------------------------------------------------
_ARBITERS: "OrderedDict[str, ChessArbiter]" = OrderedDict()
_ARB_LOCK = threading.Lock()


def arbiter_for(game_id: str) -> ChessArbiter:
    key = (game_id or "__shared__")[:80]
    with _ARB_LOCK:
        arb = _ARBITERS.get(key)
        if arb is None:
            arb = _ARBITERS[key] = ChessArbiter(fallback="random")
        _ARBITERS.move_to_end(key)
        while len(_ARBITERS) > 256:
            _ARBITERS.popitem(last=False)
        return arb


def fail(code: str, message: str):
    """Error que el cliente reconoce: el mensaje empieza por el código."""
    raise gr.Error(f"{code}: {message}", print_exception=False)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def health() -> dict:
    return {"status": "ok", "backend": "space", "ollama": "up", "models": sorted(ROSTER_IDS)}


def players() -> dict:
    out = [{**p, "kind": "llm", "available": True} for p in ROSTER]
    out.append({"model": ENGINE_ID, "name": "Motor del árbitro", "family": "engine", "kind": "engine",
                "description": "Alpha-beta prof. 2 + quiescencia, sin LLM. Línea base para comparar.",
                "available": True})
    return {"ollama": "up", "players": out}


def ai_move(fen: str, model_name: str = "vertexqwen-v3", mode: str = "pure", game_id: str = "") -> dict:
    if len(fen or "") > 120:
        fail("INVALID_FEN", "El FEN no es válido.")
    try:
        board = chess.Board(fen)
    except ValueError:
        fail("INVALID_FEN", "El FEN no es válido.")
    if not board.is_valid():
        fail("INVALID_FEN", "La posición no es legal.")
    if board.is_game_over():
        fail("GAME_OVER", "La partida ya terminó en esa posición.")
    if mode not in ("pure", "arbiter", "engine"):
        fail("BAD_MODE", "Modo desconocido.")
    engine_only = mode == "engine" or model_name == ENGINE_ID
    if not engine_only and model_name not in ROSTER_IDS:
        fail("UNKNOWN_MODEL", f"Modelo desconocido: {model_name}")

    arbiter = arbiter_for(game_id)
    t0 = time.perf_counter()
    if engine_only:
        move = arbiter.get_options(board, "arbiter")[0]
        san = board.san(move)
        res = {"move_obj": move, "move_san": san, "move_uci": move.uci(), "clean_hit": True,
               "raw_output": "motor", "mode": "engine", "options": [san]}
    else:
        _LAST_DEVICE.value = "gpu"
        res = arbiter.request_model_move(model_name, board, mode=mode, chat_fn=chat)
    think_ms = int((time.perf_counter() - t0) * 1000)

    board.push(res["move_obj"])
    return {
        "model": model_name,
        "mode": res["mode"],
        "played_san": res["move_san"],
        "played_uci": res["move_uci"],
        "clean_hit": res["clean_hit"],
        "raw_output": res["raw_output"][:300],
        "options_count": len(res.get("options", [])),
        "think_ms": think_ms,
        "device": "cpu" if engine_only else getattr(_LAST_DEVICE, "value", "gpu"),
        "new_fen": board.fen(),
        "game_over": board.is_game_over(),
        "result": board.result() if board.is_game_over() else None,
    }


with gr.Blocks(title="Vertex Chess Arena — API") as demo:
    gr.Markdown(
        "# Vertex Chess Arena — API\n"
        "Backend de la app de torneos del libro *Jaque al modelo*: Qwen 2.5 3B y Gemma 2 2B afinados "
        "con QLoRA, más el motor del árbitro.\n\n"
        + (f"**Para jugar, abre la app:** {APP_URL}\n\n" if APP_URL else "")
        + "Modelos: [vertexqwen](https://huggingface.co/Denisijcu/vertexqwen) · "
        "[vertexgemma](https://huggingface.co/Denisijcu/vertexgemma) · "
        "Código: [vertex-chess-arena](https://github.com/Denisijcu/vertex-chess-arena)"
    )
    with gr.Row():
        fen_in = gr.Textbox(label="FEN", value=chess.STARTING_FEN)
        model_in = gr.Dropdown([p["model"] for p in ROSTER] + [ENGINE_ID], value="vertexqwen-v3", label="Jugador")
        mode_in = gr.Dropdown(["pure", "arbiter", "engine"], value="pure", label="Modo")
    out = gr.JSON(label="Respuesta")
    gr.Button("Pedir jugada").click(lambda f, m, mo: ai_move(f, m, mo, "demo"), [fen_in, model_in, mode_in], out,
                                    api_name=False)
    gr.api(health, api_name="health")
    gr.api(players, api_name="players")
    gr.api(ai_move, api_name="ai_move")

demo.queue(default_concurrency_limit=4).launch()
