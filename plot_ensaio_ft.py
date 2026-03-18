"""
Gráfico do ensaio com perfil de setpoints: 40 °C → 50 °C → 35 °C
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "dados_ensaio_ft.csv"
SP_VAZAO  = 1.0

# ── Leitura e preparo ──────────────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH)

if len(df.columns) == 8:
    # Formato antigo FT
    df.columns = [
        "timestamp", "temperatura", "sp_temperatura",
        "etapa", "vazao", "dc_cooler", "dc_resistencia", "resistencia",
    ]
    if "sp_vazao" not in df.columns:
        df["sp_vazao"] = SP_VAZAO
elif len(df.columns) == 11:
    # Formato novo PID
    df.columns = [
        "timestamp", "temperatura", "sp_temperatura", "fase",
        "estab_contagem", "estab_alvo",
        "vazao", "sp_vazao", "dc_cooler", "dc_resistencia", "resistencia",
    ]
    mapa_fase = {"AQUECENDO": 1, "COOLER_ON": 2, "ESTABILIZADO": 3}
    df["etapa"] = df["fase"].map(mapa_fase).fillna(0).astype(int)
else:
    raise ValueError(
        f"Formato de CSV nao suportado ({len(df.columns)} colunas). "
        "Esperado: 8 (FT) ou 11 (PID novo)."
    )

df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0

# Instantes de transicao (mudanca no setpoint de temperatura ou etapa/fase)
mudanca_sp = df["sp_temperatura"].diff().fillna(0) != 0
mudanca_etapa = df["etapa"].diff().fillna(0) != 0
transicoes = df[mudanca_sp | mudanca_etapa]["tempo_min"].tolist()[1:]  # remove t=0

# ── Figura ─────────────────────────────────────────────────────────────────────
CORES_ETAPA = {1: "#1a9641", 2: "#d7191c", 3: "#2b83ba"}

fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
fig.suptitle(
    "Ensaio — Perfil de Setpoints: 40 °C → 50 °C → 35 °C\n"
    "PID Discreto (ZOH) | Temp Ts = 2 s | Vazão Ts = 0.2 s",
    fontsize=13, fontweight="bold", y=0.98,
)

def marcar_transicoes(ax):
    for t in transicoes:
        ax.axvline(t, color="gray", linestyle=":", linewidth=1.0, alpha=0.7)

def sombrear_etapas(ax):
    """Faixas coloridas de fundo por etapa (robusto para 1..N segmentos)."""
    limites = [0.0] + transicoes + [df["tempo_min"].iloc[-1]]
    if len(limites) < 2:
        return
    etapas_ciclo = [1, 2, 3]
    for i in range(len(limites) - 1):
        etapa = etapas_ciclo[i % len(etapas_ciclo)]
        ax.axvspan(limites[i], limites[i + 1],
                   alpha=0.06, color=CORES_ETAPA[etapa], zorder=0)

# ── Subplot 1: Temperatura ─────────────────────────────────────────────────────
ax = axes[0]
sombrear_etapas(ax)
marcar_transicoes(ax)

ax.plot(df["tempo_min"], df["temperatura"],
        color="#d62728", linewidth=0.9, label="Temperatura medida", zorder=3)
ax.step(df["tempo_min"], df["sp_temperatura"],
        color="black", linewidth=1.4, linestyle="--",
        where="post", label="Setpoint (perfil)", zorder=4)

# Anotacoes dos setpoints (conforme dados)
sp_pts = df.loc[mudanca_sp | (df.index == 0), ["tempo_min", "sp_temperatura"]]
for _, row in sp_pts.iterrows():
    t = row["tempo_min"]
    sp = row["sp_temperatura"]
    ax.annotate(f"SP = {sp:.1f} °C",
                xy=(t, sp), xytext=(t + 0.4, sp + 0.8),
                fontsize=8.5, color="black",
                arrowprops=dict(arrowstyle="->", color="black", lw=0.8))

ax.set_ylabel("Temperatura (°C)", fontsize=10)
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Temperatura", fontsize=10, loc="left")

# ── Subplot 2: Vazão ───────────────────────────────────────────────────────────
ax = axes[1]
sombrear_etapas(ax)
marcar_transicoes(ax)

media_vazao = df["vazao"].mean()

ax.plot(df["tempo_min"], df["vazao"],
        color="#1f77b4", linewidth=0.9, label="Vazão medida", zorder=3)
if "sp_vazao" in df.columns:
    ax.step(df["tempo_min"], df["sp_vazao"], color="#1f77b4", linestyle="--",
            where="post", linewidth=1.4, alpha=0.8, label="Setpoint de vazao", zorder=4)
else:
    ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--",
               linewidth=1.4, alpha=0.8, label=f"Setpoint ({SP_VAZAO} L/min)", zorder=4)
ax.axhline(media_vazao, color="#9467bd", linestyle="-.",
           linewidth=1.4, alpha=0.9, label=f"Média ({media_vazao:.2f} L/min)", zorder=4)

ax.set_ylabel("Vazão (L/min)", fontsize=10)
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Vazão", fontsize=10, loc="left")

# ── Subplot 3: Duty Cycles ─────────────────────────────────────────────────────
ax = axes[2]
sombrear_etapas(ax)
marcar_transicoes(ax)

ax.plot(df["tempo_min"], df["dc_cooler"],
        color="#2ca02c", linewidth=0.9, label="DC Cooler (PID Vazão)", zorder=3)
ax.plot(df["tempo_min"], df["dc_resistencia"],
        color="#ff7f0e", linewidth=0.9, label="DC Resistência (PID Temp)", zorder=3)

ax.set_ylabel("Duty Cycle (%)", fontsize=10)
ax.set_xlabel("Tempo (min)", fontsize=10)
ax.set_ylim(-2, 105)
ax.legend(loc="upper right", fontsize=8.5)
ax.grid(True, alpha=0.3)
ax.set_title("Sinais de Controle", fontsize=10, loc="left")

# ── Legenda global das etapas ──────────────────────────────────────────────────
patches = [
    mpatches.Patch(color=CORES_ETAPA[1], alpha=0.4, label="Etapa 1 — SP 40 °C"),
    mpatches.Patch(color=CORES_ETAPA[2], alpha=0.4, label="Etapa 2 — SP 50 °C"),
    mpatches.Patch(color=CORES_ETAPA[3], alpha=0.4, label="Etapa 3 — SP 35 °C"),
    Line2D([0], [0], color="gray", linestyle=":", linewidth=1.2, label="Transição de etapa"),
]
fig.legend(handles=patches, loc="lower center", ncol=4,
           fontsize=8.5, framealpha=0.9,
           bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.05, 1, 0.97])
plt.savefig("grafico_ensaio_ft.png", dpi=150, bbox_inches="tight")
plt.show()
print(f"Gráfico salvo em grafico_ensaio_ft.png ({len(df)} amostras, {df['tempo_min'].iloc[-1]:.1f} min)")
