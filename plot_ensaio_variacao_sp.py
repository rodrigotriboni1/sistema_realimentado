"""
Grafico do ensaio de variacao de SP:
  Fase 1 — AQUECENDO:    SP_Temp = 40 C, cooler desligado
  Fase 2 — COOLER_ON:    SP_Temp = 40 C, cooler ligado (SP_Vazao = 5 L/min)
  Fase 3 — ESTABILIZADO: ambos PIDs ativos e sistema estavel
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

CSV_PATH = "dados_ensaio_variacao_sp.csv"

CORES_FASE = {
    "AQUECENDO":    "#d7191c",
    "COOLER_ON":    "#2b83ba",
    "ESTABILIZADO": "#1a9641",
}

LABELS_FASE = {
    "AQUECENDO":    "Aquecendo (cooler OFF)",
    "COOLER_ON":    "Cooler ligado (SP = 5 L/min)",
    "ESTABILIZADO": "Estabilizado",
}

# ── Leitura ────────────────────────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH)
df.columns = [
    "timestamp", "temperatura", "sp_temperatura",
    "fase", "estab_contagem", "estab_alvo",
    "vazao", "sp_vazao",
    "dc_cooler", "dc_resistencia", "resistencia",
]
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0

# Instantes de transição de fase
ORDEM_FASES = ["AQUECENDO", "COOLER_ON", "ESTABILIZADO"]
transicoes = {}
for fase in ORDEM_FASES:
    idx = df[df["fase"] == fase].index
    if len(idx):
        transicoes[fase] = df.loc[idx[0], "tempo_min"]

t_cooler_on   = transicoes.get("COOLER_ON",   None)
t_estabilizado = transicoes.get("ESTABILIZADO", None)
t_fim = df["tempo_min"].iloc[-1]

def sombrear_fases(ax):
    limites = [0.0]
    if t_cooler_on:
        limites.append(t_cooler_on)
    if t_estabilizado:
        limites.append(t_estabilizado)
    limites.append(t_fim)

    fases_presentes = [f for f in ORDEM_FASES if f in transicoes]
    for i, fase in enumerate(fases_presentes):
        if i < len(limites) - 1:
            ax.axvspan(limites[i], limites[i + 1],
                       alpha=0.07, color=CORES_FASE[fase], zorder=0)

def marcar_transicoes(ax):
    for t in [t_cooler_on, t_estabilizado]:
        if t is not None:
            ax.axvline(t, color="gray", linestyle=":", linewidth=1.1, alpha=0.8)

# ── Figura ─────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(4, 1, figsize=(14, 13), sharex=True)
fig.suptitle(
    "Ensaio — Variacao de SP do Cooler\n"
    "SP_Temp = 40 C (fixo) | Cooler: OFF -> SP = 5 L/min apos estabilizacao",
    fontsize=12, fontweight="bold", y=0.99,
)

# ── Subplot 1: Temperatura ─────────────────────────────────────────────────────
ax = axes[0]
sombrear_fases(ax)
marcar_transicoes(ax)
ax.plot(df["tempo_min"], df["temperatura"],
        color="#d62728", linewidth=0.9, label="Temperatura medida", zorder=3)
ax.axhline(40.0, color="black", linestyle="--", linewidth=1.3,
           alpha=0.8, label="Setpoint (40 C)", zorder=4)
ax.axhspan(39.5, 40.5, color="#d62728", alpha=0.08, label="Faixa +/-0.5 C")

if t_cooler_on:
    ax.annotate("Cooler ligado",
                xy=(t_cooler_on, 40), xytext=(t_cooler_on + 0.5, 38.5),
                fontsize=8.5, color=CORES_FASE["COOLER_ON"],
                arrowprops=dict(arrowstyle="->", color=CORES_FASE["COOLER_ON"], lw=0.9))

ax.set_ylabel("Temperatura (C)", fontsize=10)
ax.legend(loc="lower right", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Temperatura", fontsize=10, loc="left")

# ── Subplot 2: Vazao ───────────────────────────────────────────────────────────
ax = axes[1]
sombrear_fases(ax)
marcar_transicoes(ax)
ax.plot(df["tempo_min"], df["vazao"],
        color="#1f77b4", linewidth=0.9, label="Vazao medida", zorder=3)
ax.step(df["tempo_min"], df["sp_vazao"],
        color="black", linewidth=1.3, linestyle="--", where="post",
        label="Setpoint vazao", zorder=4)

media_vazao_cooler = df.loc[df["fase"] != "AQUECENDO", "vazao"].mean()
if not pd.isna(media_vazao_cooler):
    ax.axhline(media_vazao_cooler, color="#9467bd", linestyle="-.",
               linewidth=1.2, alpha=0.9,
               label=f"Media (cooler ON) = {media_vazao_cooler:.2f} L/min", zorder=4)

ax.set_ylabel("Vazao (L/min)", fontsize=10)
ax.legend(loc="upper left", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Vazao", fontsize=10, loc="left")

# ── Subplot 3: Duty Cycles ─────────────────────────────────────────────────────
ax = axes[2]
sombrear_fases(ax)
marcar_transicoes(ax)
ax.plot(df["tempo_min"], df["dc_cooler"],
        color="#2ca02c", linewidth=0.9, label="DC Cooler (PID Vazao)", zorder=3)
ax.plot(df["tempo_min"], df["dc_resistencia"],
        color="#ff7f0e", linewidth=0.9, label="DC Resistencia (PID Temp)", zorder=3)
ax.set_ylabel("Duty Cycle (%)", fontsize=10)
ax.set_ylim(-2, 105)
ax.legend(loc="center right", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Sinais de Controle", fontsize=10, loc="left")

# ── Subplot 4: Contador de estabilizacao ──────────────────────────────────────
ax = axes[3]
sombrear_fases(ax)
marcar_transicoes(ax)
alvo = int(df["estab_alvo"].iloc[0])
ax.step(df["tempo_min"], df["estab_contagem"],
        color="#8c564b", linewidth=0.9, where="post", label="Contagem estab.", zorder=3)
ax.axhline(alvo, color="black", linestyle="--", linewidth=1.1,
           alpha=0.7, label=f"Alvo ({alvo} leituras)", zorder=4)
ax.set_ylabel("Contagem", fontsize=10)
ax.set_xlabel("Tempo (min)", fontsize=10)
ax.set_ylim(-0.3, alvo + 1.5)
ax.set_yticks(range(alvo + 2))
ax.legend(loc="upper left", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Progresso de Estabilizacao", fontsize=10, loc="left")

# ── Legenda global das fases ───────────────────────────────────────────────────
patches = [
    mpatches.Patch(color=CORES_FASE["AQUECENDO"],    alpha=0.4, label=LABELS_FASE["AQUECENDO"]),
    mpatches.Patch(color=CORES_FASE["COOLER_ON"],    alpha=0.4, label=LABELS_FASE["COOLER_ON"]),
    mpatches.Patch(color=CORES_FASE["ESTABILIZADO"], alpha=0.4, label=LABELS_FASE["ESTABILIZADO"]),
    Line2D([0], [0], color="gray", linestyle=":", linewidth=1.3, label="Transicao de fase"),
]
fig.legend(handles=patches, loc="lower center", ncol=4,
           fontsize=8.5, framealpha=0.9, bbox_to_anchor=(0.5, 0.005))

plt.tight_layout(rect=[0, 0.04, 1, 0.97])
plt.savefig("grafico_ensaio_variacao_sp.png", dpi=150, bbox_inches="tight")
plt.show()

dur = df["tempo_min"].iloc[-1]
print(f"Grafico salvo em grafico_ensaio_variacao_sp.png")
print(f"  {len(df)} amostras | {dur:.1f} min total")
for fase in ORDEM_FASES:
    n = (df["fase"] == fase).sum()
    if n:
        print(f"  {fase}: {n} amostras ({n*2/60:.1f} min)")
