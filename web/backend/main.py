"""
API FastAPI - Fase 1 + 2 + 3: upload, controle e streaming em tempo real.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analysis import run_analysis

app = FastAPI(title="Plataforma Ensaios Térmicos", version="1.0")

# CORS: em produção defina CORS_ORIGINS (ex: "http://localhost:8000,https://meudominio.com")
_cors_origins = os.environ.get("CORS_ORIGINS", "*")
allow_origins = [o.strip() for o in _cors_origins.split(",")] if _cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Limite de upload (10 MB); fallback se env inválido
try:
    MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
except (TypeError, ValueError):
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Pasta para uploads (relativa ao backend)
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Estado de controle (Fase 2): resistência e cooler 0-100%, em memória
control_state = {"resistencia": 0, "cooler": 0}

# Fase 3: última amostra e conexões WebSocket para streaming
last_sample = None
websocket_connections = []


class SampleRequest(BaseModel):
    temperatura: float
    vazao: float
    cooler: int
    resistencia: str  # "ON" | "OFF"
    timestamp: str | None = None


class AnalyzeRequest(BaseModel):
    test_id: str
    tipo: str  # "temperatura" | "fluxo"


class ControlRequest(BaseModel):
    resistencia: int | None = None  # 0-100
    cooler: int | None = None  # 0-100


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """Faz upload de um CSV e salva com ID único. Tamanho máximo configurável por MAX_UPLOAD_BYTES."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Envie um arquivo .csv")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Arquivo muito grande. Máximo: {MAX_UPLOAD_BYTES // (1024*1024)} MB")
    content = raw.decode("utf-8", errors="replace")
    # Validar cabeçalho
    if "temperatura_C" not in content or "timestamp" not in content:
        raise HTTPException(400, "CSV deve ter colunas: timestamp, temperatura_C, vazao_L_min, cooler_%, resistencia")
    test_id = str(uuid.uuid4())
    path = UPLOAD_DIR / f"{test_id}.csv"
    path.write_text(content, encoding="utf-8")
    meta = {"filename": file.filename or "dados.csv"}
    (UPLOAD_DIR / f"{test_id}.meta").write_text(json.dumps(meta), encoding="utf-8")
    return {"id": test_id, "filename": meta["filename"]}


def _test_meta(test_id: str) -> dict:
    meta_path = UPLOAD_DIR / f"{test_id}.meta"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"filename": f"{test_id}.csv"}


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


@app.get("/api/tests")
def list_tests():
    """Lista todos os testes (CSVs) enviados."""
    tests = []
    try:
        files = sorted(UPLOAD_DIR.glob("*.csv"), key=lambda p: -_safe_mtime(p))
    except OSError:
        return {"tests": []}
    for f in files:
        try:
            meta = _test_meta(f.stem)
            tests.append({
                "id": f.stem,
                "filename": meta.get("filename", f.name),
            })
        except OSError:
            continue
    return {"tests": tests}


@app.get("/api/tests/{test_id}/analyze")
def analyze_test(test_id: str, tipo: str):
    """
    tipo: temperatura | fluxo
    Retorna dados para gráfico e parâmetros da função de transferência.
    """
    path = UPLOAD_DIR / f"{test_id}.csv"
    if not path.exists():
        raise HTTPException(404, "Teste não encontrado")
    if tipo not in ("temperatura", "fluxo", "perturbacao"):
        raise HTTPException(400, "tipo deve ser 'temperatura', 'fluxo' ou 'perturbacao'")
    content = path.read_text(encoding="utf-8")
    try:
        return run_analysis(content, tipo)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"CSV inválido ou formato não suportado: {e!s}")


@app.get("/api/control")
def get_control():
    """Retorna o estado atual de controle (ESP32 chama para obter setpoint)."""
    return control_state


@app.get("/api/sample")
def get_sample():
    """Retorna a última amostra recebida (Fase 3)."""
    return last_sample


def _now_utc_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@app.post("/api/sample")
async def post_sample(body: SampleRequest):
    """Recebe uma amostra (ponte ou ESP32) e envia a todos os clientes WebSocket."""
    global last_sample
    if body.resistencia.upper() not in ("ON", "OFF"):
        raise HTTPException(400, "resistencia deve ser ON ou OFF")
    # Validação: cooler 0-100; temperatura e vazão em faixas razoáveis (rejeitar só absurdos)
    cooler = max(0, min(100, body.cooler))
    if not (-50 <= body.temperatura <= 150):
        raise HTTPException(400, "temperatura fora da faixa esperada (-50 a 150 °C)")
    if body.vazao < 0 or body.vazao > 100:
        raise HTTPException(400, "vazao fora da faixa esperada (0 a 100 L/min)")
    sample = {
        "timestamp": body.timestamp or _now_utc_iso(),
        "temperatura": body.temperatura,
        "vazao": body.vazao,
        "cooler": cooler,
        "resistencia": body.resistencia.upper(),
    }
    last_sample = sample
    dead = []
    for ws in websocket_connections:
        try:
            await ws.send_json(sample)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in websocket_connections:
            websocket_connections.remove(ws)
    return {"ok": True}


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    """Conexão WebSocket para receber amostras em tempo real (Fase 3)."""
    await websocket.accept()
    websocket_connections.append(websocket)
    try:
        if last_sample is not None:
            await websocket.send_json(last_sample)
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        if websocket in websocket_connections:
            websocket_connections.remove(websocket)


@app.post("/api/control")
def post_control(body: ControlRequest):
    """Atualiza resistência e/ou cooler (0-100). Frontend envia ao alterar controles."""
    global control_state
    if body.resistencia is not None:
        control_state["resistencia"] = max(0, min(100, body.resistencia))
    if body.cooler is not None:
        control_state["cooler"] = max(0, min(100, body.cooler))
    return control_state


@app.post("/api/analyze")
async def analyze_direct(file: UploadFile = File(...), tipo: str = "temperatura"):
    """
    Analisa um CSV enviado diretamente sem salvar.
    tipo: temperatura | fluxo (query param)
    """
    if tipo not in ("temperatura", "fluxo", "perturbacao"):
        raise HTTPException(400, "tipo deve ser 'temperatura', 'fluxo' ou 'perturbacao'")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Arquivo muito grande. Máximo: {MAX_UPLOAD_BYTES // (1024*1024)} MB")
    content = raw.decode("utf-8", errors="replace")
    if "temperatura_C" not in content:
        raise HTTPException(400, "CSV inválido")
    try:
        return run_analysis(content, tipo)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, f"CSV inválido ou formato não suportado: {e!s}")


@app.get("/")
def index():
    """Frontend SPA."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "API Ensaios. Coloque o frontend em web/static/."}


# Monta arquivos estáticos (JS, CSS, etc.)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
