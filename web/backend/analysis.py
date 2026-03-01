"""
Módulo de análise FOPDT para temperatura e fluxo.
Parse de CSV e identificação da função de transferência.
"""

import csv
import io
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import curve_fit


REQUIRED_CSV_COLUMNS = ("timestamp", "temperatura_C", "vazao_L_min", "cooler_%", "resistencia")
TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"


def parse_csv(content: str) -> Tuple[List[float], List[float], List[float], List[int], List[int]]:
    """
    Parse CSV (string) com colunas: timestamp, temperatura_C, vazao_L_min, cooler_%, resistencia.
    Retorna: tempo_s, temperatura, vazao, cooler, resistencia
    """
    tempo, temp, vazao, cooler, resistencia = [], [], [], [], []
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV sem cabeçalho")
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(missing)}")
    t0 = None
    for row in reader:
        ts = datetime.strptime(row["timestamp"].strip(), TIMESTAMP_FMT)
        if t0 is None:
            t0 = ts
        tempo.append((ts - t0).total_seconds())
        temp.append(float(row["temperatura_C"]))
        vazao.append(float(row["vazao_L_min"]))
        cooler.append(int(row["cooler_%"]))
        resistencia.append(1 if row["resistencia"].strip().upper() == "ON" else 0)
    if not tempo:
        raise ValueError("CSV sem linhas de dados")
    return tempo, temp, vazao, cooler, resistencia


def modelo_fopdt(t: np.ndarray, K: float, tau: float, L: float) -> np.ndarray:
    """Resposta ao degrau FOPDT: y(t) = K*(1 - exp(-(t-L)/tau)) para t > L."""
    y = np.zeros_like(t)
    mask = t > L
    y[mask] = K * (1 - np.exp(-(t[mask] - L) / tau))
    return y


def identificar_fopdt(t: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """Ajuste FOPDT. Retorna K, tau, L."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    y_final = np.mean(y[-20:]) if len(y) >= 20 else y[-1]
    K_est = float(y_final)
    tau_est = (t[-1] - t[0]) / 3 if len(t) > 1 else 10.0
    L_est = 0.0
    try:
        popt, _ = curve_fit(
            modelo_fopdt,
            t,
            y,
            p0=[K_est, tau_est, L_est],
            bounds=([-1000, 0.1, 0], [1000, 10000, 120]),
            maxfev=10000,
        )
        return float(popt[0]), float(popt[1]), float(popt[2])
    except Exception:
        return K_est, tau_est, L_est


def analyze_temperature(
    tempo: List[float], temp: List[float]
) -> Dict[str, Any]:
    """
    G_T(s): Resistência -> Temperatura.
    Step em t=0, delta_T = T(t) - T(0).
    """
    t = np.array(tempo)
    T0 = temp[0]
    y = np.array(temp) - T0
    K, tau, L = identificar_fopdt(t, y)
    y_ajuste = modelo_fopdt(t, K, tau, L)
    return {
        "tipo": "temperatura",
        "entrada": "Resistência PWM",
        "saida": "Temperatura (°C)",
        "ref_inicial": T0,
        "tempo": t.tolist(),
        "dado": np.array(temp).tolist(),
        "delta": y.tolist(),
        "ajuste": y_ajuste.tolist(),
        "K": round(K, 4),
        "tau": round(tau, 2),
        "L": round(L, 2),
        "formula": f"G_T(s) = {K:.4f} * exp(-{L:.2f}s) / ({tau:.2f}s + 1)",
    }


def analyze_flow(
    tempo: List[float], vazao: List[float]
) -> Dict[str, Any]:
    """
    G_F(s): Cooler -> Fluxo (vazão).
    Step em t=0, delta_Q = Q(t) - Q(0).
    """
    t = np.array(tempo)
    Q0 = vazao[0]
    y = np.array(vazao) - Q0
    K, tau, L = identificar_fopdt(t, y)
    y_ajuste = modelo_fopdt(t, K, tau, L)
    return {
        "tipo": "fluxo",
        "entrada": "Cooler PWM",
        "saida": "Vazão (L/min)",
        "ref_inicial": Q0,
        "tempo": t.tolist(),
        "dado": np.array(vazao).tolist(),
        "delta": y.tolist(),
        "ajuste": y_ajuste.tolist(),
        "K": round(K, 4),
        "tau": round(tau, 2),
        "L": round(L, 2),
        "formula": f"G_F(s) = {K:.4f} * exp(-{L:.2f}s) / ({tau:.2f}s + 1)",
    }


def analyze_perturbation(
    tempo: List[float], temp: List[float]
) -> Dict[str, Any]:
    """
    G_FT(s): Cooler (perturbação) -> Temperatura de saída.
    Resposta da temperatura ao degrau no cooler (resistência em regime).
    """
    t = np.array(tempo)
    T0 = temp[0]
    y = np.array(temp) - T0
    K, tau, L = identificar_fopdt(t, y)
    y_ajuste = modelo_fopdt(t, K, tau, L)
    return {
        "tipo": "perturbacao",
        "entrada": "Cooler PWM (perturbação)",
        "saida": "Temperatura (°C)",
        "ref_inicial": T0,
        "tempo": t.tolist(),
        "dado": np.array(temp).tolist(),
        "delta": y.tolist(),
        "ajuste": y_ajuste.tolist(),
        "K": round(K, 4),
        "tau": round(tau, 2),
        "L": round(L, 2),
        "formula": f"G_FT(s) = {K:.4f} * exp(-{L:.2f}s) / ({tau:.2f}s + 1)",
    }


def run_analysis(csv_content: str, tipo: str) -> Dict[str, Any]:
    """
    tipo: "temperatura" | "fluxo" | "perturbacao"
    Retorna resultado da análise para o frontend.
    Levanta ValueError se o CSV for inválido ou tipo incorreto.
    """
    if tipo not in ("temperatura", "fluxo", "perturbacao"):
        raise ValueError("tipo deve ser 'temperatura', 'fluxo' ou 'perturbacao'")
    tempo, temp, vazao, cooler, resistencia = parse_csv(csv_content)
    if tipo == "temperatura":
        return analyze_temperature(tempo, temp)
    if tipo == "fluxo":
        return analyze_flow(tempo, vazao)
    return analyze_perturbation(tempo, temp)
