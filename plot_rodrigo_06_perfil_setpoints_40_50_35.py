"""
Gera grafico para data/rodrigo_raw/06_ensaio_perfil_setpoints_40_50_35.csv.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

CSV_DEFAULT = Path("data/rodrigo_raw/06_ensaio_perfil_setpoints_40_50_35.csv")
PLOTS_DIR = Path("plots")
SP_VAZAO = 1.0
CORES_ETAPA = {1: "#1a9641", 2: "#d7191c", 3: "#2b83ba"}

csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_DEFAULT
df = pd.read_csv(csv_path)
df = df.rename(
    columns={
        "temperatura_C": "temperatura",
        "sp_temperatura_C": "sp_temperatura",
        "vazao_L_min": "vazao",
        "dc_cooler_%": "dc_cooler",
        "dc_resistencia_%": "dc_resistencia",
    }
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0
transicoes = df[df["etapa"].diff() != 0]["tempo_min"].tolist()[1:]

fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
fig.suptitle(
    "Rodrigo 06: Perfil de Setpoints 40 C -> 50 C -> 35 C",
    fontsize=13,
    fontweight="bold",
    y=0.98,
)

def marcar_transicoes(ax):
    for t in transicoes:
        ax.axvline(t, color="gray", linestyle=":", linewidth=1.0, alpha=0.7)

def sombrear_etapas(ax):
    limites = [0.0] + transicoes + [df["tempo_min"].iloc[-1]]
    for i, etapa in enumerate([1, 2, 3]):
        ax.axvspan(limites[i], limites[i + 1], alpha=0.06, color=CORES_ETAPA[etapa], zorder=0)

ax = axes[0]
sombrear_etapas(ax)
marcar_transicoes(ax)
ax.plot(df["tempo_min"], df["temperatura"], color="#d62728", linewidth=0.9, label="Temperatura", zorder=3)
ax.step(df["tempo_min"], df["sp_temperatura"], color="black", linewidth=1.4, linestyle="--", where="post", label="Setpoint", zorder=4)
ax.set_ylabel("Temperatura (C)")
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)

ax = axes[1]
sombrear_etapas(ax)
marcar_transicoes(ax)
media_vazao = df["vazao"].mean()
ax.plot(df["tempo_min"], df["vazao"], color="#1f77b4", linewidth=0.9, label="Vazao", zorder=3)
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", linewidth=1.4, alpha=0.8, label=f"SP ({SP_VAZAO} L/min)", zorder=4)
ax.axhline(media_vazao, color="#9467bd", linestyle="-.", linewidth=1.4, alpha=0.9, label=f"Media ({media_vazao:.2f} L/min)", zorder=4)
ax.set_ylabel("Vazao (L/min)")
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)

ax = axes[2]
sombrear_etapas(ax)
marcar_transicoes(ax)
ax.plot(df["tempo_min"], df["dc_cooler"], color="#2ca02c", linewidth=0.9, label="DC Cooler", zorder=3)
ax.plot(df["tempo_min"], df["dc_resistencia"], color="#ff7f0e", linewidth=0.9, label="DC Resistencia", zorder=3)
ax.set_ylabel("Duty Cycle (%)")
ax.set_xlabel("Tempo (min)")
ax.set_ylim(-2, 105)
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)

patches = [
    mpatches.Patch(color=CORES_ETAPA[1], alpha=0.4, label="Etapa 1 - SP 40 C"),
    mpatches.Patch(color=CORES_ETAPA[2], alpha=0.4, label="Etapa 2 - SP 50 C"),
    mpatches.Patch(color=CORES_ETAPA[3], alpha=0.4, label="Etapa 3 - SP 35 C"),
    Line2D([0], [0], color="gray", linestyle=":", linewidth=1.2, label="Transicao"),
]
fig.legend(handles=patches, loc="lower center", ncol=4, fontsize=8.5, framealpha=0.9, bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.05, 1, 0.97])
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
output_path = PLOTS_DIR / "rodrigo_06_perfil_setpoints_40_50_35.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
plt.show()
print(f"Grafico salvo em {output_path} ({len(df)} amostras)")
