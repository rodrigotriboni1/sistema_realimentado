"""
Analisa e plota os dados do experimento PID novo.

Saidas:
1) grafico_ensaio_pid_novo.png
2) resumo_ensaio_pid_novo.txt
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "dados_ensaio_pid_novo.csv"
IMG_OUT = "grafico_ensaio_pid_novo.png"
TXT_OUT = "resumo_ensaio_pid_novo.txt"

ORDEM_FASES = ["AQUECENDO", "COOLER_ON", "ESTABILIZADO"]
CORES_FASE = {
    "AQUECENDO": "#d7191c",
    "COOLER_ON": "#2b83ba",
    "ESTABILIZADO": "#1a9641",
}


def settling_time(tempo_s: np.ndarray, erro_abs: np.ndarray, banda: float) -> float:
    """Retorna o primeiro instante em que permanece dentro da banda ate o fim."""
    dentro = erro_abs <= banda
    for i in range(len(dentro)):
        if dentro[i] and np.all(dentro[i:]):
            return float(tempo_s[i])
    return float("nan")


def fase_metrics(df: pd.DataFrame, fase: str) -> dict:
    sub = df[df["fase"] == fase].copy()
    if sub.empty:
        return {}

    sub["erro_temp"] = sub["sp_temperatura"] - sub["temperatura"]
    sub["erro_vazao"] = sub["sp_vazao"] - sub["vazao"]

    t_s = sub["tempo_s"].to_numpy()
    err_t = sub["erro_temp"].to_numpy()
    err_f = sub["erro_vazao"].to_numpy()

    temp_abs = np.abs(err_t)
    vazao_abs = np.abs(err_f)

    met = {
        "fase": fase,
        "n": len(sub),
        "duracao_s": float(t_s[-1] - t_s[0]) if len(sub) > 1 else 0.0,
        "temp_media": float(sub["temperatura"].mean()),
        "temp_mae": float(temp_abs.mean()),
        "temp_rmse": float(np.sqrt(np.mean(err_t ** 2))),
        "temp_max_overshoot": float((sub["temperatura"] - sub["sp_temperatura"]).max()),
        "temp_settling_s_0p5": settling_time(t_s - t_s[0], temp_abs, banda=0.5),
        "vazao_media": float(sub["vazao"].mean()),
        "vazao_mae": float(vazao_abs.mean()),
        "vazao_rmse": float(np.sqrt(np.mean(err_f ** 2))),
        "vazao_max_overshoot": float((sub["vazao"] - sub["sp_vazao"]).max()),
        "vazao_settling_s_0p4": settling_time(t_s - t_s[0], vazao_abs, banda=0.4),
        "dc_cooler_medio": float(sub["dc_cooler"].mean()),
        "dc_resist_medio": float(sub["dc_resistencia"].mean()),
    }
    return met


def fmt_num(x: float, nd: int = 3) -> str:
    if pd.isna(x):
        return "n/a"
    return f"{x:.{nd}f}"


def main() -> None:
    csv_file = Path(CSV_PATH)
    if not csv_file.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {CSV_PATH}")

    df = pd.read_csv(csv_file)
    df.columns = [
        "timestamp",
        "temperatura",
        "sp_temperatura",
        "fase",
        "estab_contagem",
        "estab_alvo",
        "vazao",
        "sp_vazao",
        "dc_cooler",
        "dc_resistencia",
        "resistencia",
    ]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    t0 = df["timestamp"].iloc[0]
    df["tempo_s"] = (df["timestamp"] - t0).dt.total_seconds()
    df["tempo_min"] = df["tempo_s"] / 60.0

    # Metricas globais
    df["erro_temp"] = df["sp_temperatura"] - df["temperatura"]
    df["erro_vazao"] = df["sp_vazao"] - df["vazao"]
    mae_temp_global = float(np.abs(df["erro_temp"]).mean())
    mae_vazao_global = float(np.abs(df["erro_vazao"]).mean())

    # Metricas por fase
    metrics = [fase_metrics(df, f) for f in ORDEM_FASES if not df[df["fase"] == f].empty]

    # Plot
    fig, axes = plt.subplots(4, 1, figsize=(14, 13), sharex=True)
    fig.suptitle(
        "Ensaio PID Novo - Temperatura e Vazao\n"
        "Fases: AQUECENDO -> COOLER_ON -> ESTABILIZADO",
        fontsize=12,
        fontweight="bold",
        y=0.99,
    )

    # Regioes por fase
    for fase in ORDEM_FASES:
        idx = df[df["fase"] == fase].index
        if len(idx):
            x0 = df.loc[idx[0], "tempo_min"]
            x1 = df.loc[idx[-1], "tempo_min"]
            for ax in axes:
                ax.axvspan(x0, x1, alpha=0.07, color=CORES_FASE[fase], zorder=0)

    # Temperatura
    ax = axes[0]
    ax.plot(df["tempo_min"], df["temperatura"], color="#d62728", lw=0.9, label="Temperatura")
    ax.step(df["tempo_min"], df["sp_temperatura"], where="post", color="black", ls="--", lw=1.2, label="SP Temp")
    ax.axhspan(df["sp_temperatura"].median() - 0.5, df["sp_temperatura"].median() + 0.5, color="#d62728", alpha=0.08, label="Banda +/-0.5 C")
    ax.set_ylabel("Temp (C)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8.5)

    # Vazao
    ax = axes[1]
    ax.plot(df["tempo_min"], df["vazao"], color="#1f77b4", lw=0.9, label="Vazao")
    ax.step(df["tempo_min"], df["sp_vazao"], where="post", color="black", ls="--", lw=1.2, label="SP Vazao")
    ax.axhspan(df["sp_vazao"].median() - 0.4, df["sp_vazao"].median() + 0.4, color="#1f77b4", alpha=0.08, label="Banda +/-0.4 L/min")
    ax.set_ylabel("Vazao (L/min)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8.5)

    # Duty cycles
    ax = axes[2]
    ax.plot(df["tempo_min"], df["dc_cooler"], color="#2ca02c", lw=0.9, label="DC Cooler")
    ax.plot(df["tempo_min"], df["dc_resistencia"], color="#ff7f0e", lw=0.9, label="DC Resistencia")
    ax.set_ylabel("Duty (%)")
    ax.set_ylim(-2, 105)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8.5)

    # Erros absolutos
    ax = axes[3]
    ax.plot(df["tempo_min"], np.abs(df["erro_temp"]), color="#9467bd", lw=0.9, label="|erro temp|")
    ax.plot(df["tempo_min"], np.abs(df["erro_vazao"]), color="#8c564b", lw=0.9, label="|erro vazao|")
    ax.axhline(0.5, color="#9467bd", ls="--", lw=1.0, alpha=0.6, label="Banda temp 0.5")
    ax.axhline(0.4, color="#8c564b", ls="--", lw=1.0, alpha=0.6, label="Banda vazao 0.4")
    ax.set_ylabel("Erro abs.")
    ax.set_xlabel("Tempo (min)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8.5)

    plt.tight_layout(rect=[0, 0.02, 1, 0.96])
    plt.savefig(IMG_OUT, dpi=150, bbox_inches="tight")
    plt.close()

    # Relatorio txt
    linhas = []
    linhas.append("RESUMO DO ENSAIO PID NOVO")
    linhas.append("=" * 32)
    linhas.append(f"Amostras: {len(df)}")
    linhas.append(f"Duracao total: {fmt_num(df['tempo_s'].iloc[-1], 1)} s")
    linhas.append(f"MAE temp global: {fmt_num(mae_temp_global, 3)} C")
    linhas.append(f"MAE vazao global: {fmt_num(mae_vazao_global, 3)} L/min")
    linhas.append("")
    linhas.append("METRICAS POR FASE")
    linhas.append("-" * 32)

    for m in metrics:
        linhas.append(f"Fase: {m['fase']}")
        linhas.append(f"  amostras: {m['n']} | duracao: {fmt_num(m['duracao_s'], 1)} s")
        linhas.append(
            f"  temp media: {fmt_num(m['temp_media'])} C | MAE: {fmt_num(m['temp_mae'])} | RMSE: {fmt_num(m['temp_rmse'])}"
        )
        linhas.append(
            f"  temp overshoot max: {fmt_num(m['temp_max_overshoot'])} C | settling(+-0.5C): {fmt_num(m['temp_settling_s_0p5'], 1)} s"
        )
        linhas.append(
            f"  vazao media: {fmt_num(m['vazao_media'])} L/min | MAE: {fmt_num(m['vazao_mae'])} | RMSE: {fmt_num(m['vazao_rmse'])}"
        )
        linhas.append(
            f"  vazao overshoot max: {fmt_num(m['vazao_max_overshoot'])} L/min | settling(+-0.4): {fmt_num(m['vazao_settling_s_0p4'], 1)} s"
        )
        linhas.append(
            f"  DC medio cooler: {fmt_num(m['dc_cooler_medio'], 2)}% | DC medio resistencia: {fmt_num(m['dc_resist_medio'], 2)}%"
        )
        linhas.append("")

    Path(TXT_OUT).write_text("\n".join(linhas), encoding="utf-8")

    print(f"Grafico salvo em: {IMG_OUT}")
    print(f"Resumo salvo em: {TXT_OUT}")
    print(f"Amostras: {len(df)} | duracao: {fmt_num(df['tempo_s'].iloc[-1], 1)} s")


if __name__ == "__main__":
    main()
