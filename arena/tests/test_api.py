"""Tests de la API V3 (no necesitan Ollama: se simula).
Correr desde E:\\vertex-chess-arena\\arena :
    ..\\venv\\Scripts\\python.exe -m pytest -q tests
"""
import io
import json
import sys
from pathlib import Path

import chess
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import api_server  # noqa: E402
import engine_arbiter  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._b


def fake_ollama(answer_last_option=True):
    def _urlopen(req, timeout=0):
        url = req if isinstance(req, str) else req.full_url
        if url.endswith("/api/tags"):
            return _Resp({"models": [{"name": "vertexqwen-v3:latest"}, {"name": "vertexgemma:latest"}]})
        body = json.loads(req.data)
        user = body["messages"][-1]["content"]
        opts = user.split("Legal moves (SAN): ")[1].split("\n")[0].split(", ")
        return _Resp({"message": {"content": f"Best move: {opts[-1] if answer_last_option else 'zz'}"}})
    return _urlopen


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server, "DATA_DIR", tmp_path)
    monkeypatch.setattr(api_server, "GAMES_LOG", tmp_path / "arena_games.jsonl")
    monkeypatch.setattr(api_server, "PGN_LOG", tmp_path / "matches_history.pgn")
    monkeypatch.setattr(api_server, "TOURNAMENTS_DIR", tmp_path / "tournaments")
    monkeypatch.setattr(api_server.urllib.request, "urlopen", fake_ollama())
    monkeypatch.setattr(engine_arbiter.urllib.request, "urlopen", fake_ollama())
    return TestClient(api_server.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ollama"] == "up"


def test_players_marks_availability(client):
    players = {p["model"]: p for p in client.get("/api/players").json()["players"]}
    assert players["vertexqwen-v3"]["available"] is True
    assert players["vertexqwen"]["available"] is False
    assert players["vertex-engine"]["kind"] == "engine"


def test_ai_move_pure(client):
    r = client.post("/api/ai-move", json={"fen": chess.STARTING_FEN, "model_name": "vertexgemma", "mode": "pure", "game_id": "g1"})
    body = r.json()
    assert r.status_code == 200, body
    assert body["clean_hit"] is True and body["options_count"] == 20
    assert chess.Board(body["new_fen"]).fullmove_number == 1


def test_ai_move_engine_mode_needs_no_llm(client, monkeypatch):
    monkeypatch.setattr(engine_arbiter.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    r = client.post("/api/ai-move", json={"fen": chess.STARTING_FEN, "model_name": "vertex-engine", "mode": "engine"})
    assert r.status_code == 200 and r.json()["mode"] == "engine"


def test_ai_move_ollama_down_is_503(client, monkeypatch):
    monkeypatch.setattr(engine_arbiter.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    r = client.post("/api/ai-move", json={"fen": chess.STARTING_FEN, "model_name": "vertexgemma"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_UNAVAILABLE"


def test_invalid_fen_and_unknown_model(client):
    assert client.post("/api/ai-move", json={"fen": "nope", "model_name": "vertexgemma"}).json()["error"]["code"] == "INVALID_FEN"
    assert client.post("/api/ai-move", json={"fen": chess.STARTING_FEN, "model_name": "gpt"}).json()["error"]["code"] == "UNKNOWN_MODEL"


def test_save_and_list_games(client):
    pgn = '[White "a"]\n[Black "b"]\n[Result "1-0"]\n\n1. f3 e5 2. g4 Qh4# 0-1\n'
    payload = {"pgn": pgn, "white": "a", "black": "b", "result": "0-1", "termination": "checkmate",
               "time_control": "60+0", "plies": 4}
    assert client.post("/api/games", json=payload).status_code == 201
    games = client.get("/api/games").json()
    assert len(games) == 1 and games[0]["result"] == "0-1"


def test_tournament_roundtrip_and_path_safety(client):
    t = {"id": "abc123", "name": "Copa", "format": "round-robin", "status": "running", "participants": [1, 2]}
    assert client.put("/api/tournaments/abc123", json=t).status_code == 200
    assert client.get("/api/tournaments/abc123").json()["name"] == "Copa"
    assert client.get("/api/tournaments").json()[0]["players"] == 2
    assert client.put("/api/tournaments/xyz999", json=t).status_code == 400  # id distinto
    assert client.get("/api/tournaments/..%2F..%2Fsecret").status_code in (400, 404)
