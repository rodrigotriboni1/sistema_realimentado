"""
Comparação entre dois ensaios FT: dados_ensaio_ft.csv vs dados_ensaio_ft_final.csv
Gera 2 gráficos lado a lado mostrando as diferenças.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

CSV_ORIGINAL = "dados_ensaio_ft.csv"
CSV_FINAL = "dados_ensaio_ft_final.csv"
SP_VAZAO = 1.0
CORES_ETAPA = {1: "#1a9641", 2: "#d7191c", 3: "#2b83ba"}


def carregar_ensaio(path: str):
    """Carrega CSV e normaliza colunas. Retorna df com tempo_min e metadados."""
    df = pd.read_csv(path)
    # Normalizar nomes de colunas (ambos CSVs podem ter sufixos _C, _%, etc.)
    rename = {}
    for c in df.columns:
        if "timestamp" in c.lower() or c == "timestamp":
            rename[c] = "timestamp"
        elif "temperatura" in c.lower() and "sp" not in c.lower():
            rename[c] = "temperatura"
        elif "sp_temperatura" in c.lower() or "sp_temperatura" in c:
            rename[c] = "sp_temperatura"
        elif c == "etapa":
            rename[c] = "etapa"
        elif "vazao" in c.lower():
            rename[c] = "vazao"
        elif "dc_cooler" in c.lower():
            rename[c] = "dc_cooler"
        elif "dc_resistencia" in c.lower():
            rename[c] = "dc_resistencia"
        elif "resistencia" in c.lower():
            rename[c] = "resistencia"
    df = df.rename(columns=rename)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0
    return df


def transicoes_etapas(df):
    if "etapa" not in df.columns:
        return []
    diff = df["etapa"].diff()
    return df.loc[diff != 0, "tempo_min"].tolist()[1:]


def sombrear_etapas(ax, df, transicoes):
    if not transicoes or "etapa" not in df.columns:
        return
    limites = [df["tempo_min"].iloc[0]] + transicoes + [df["tempo_min"].iloc[-1]]
    etapas_unicas = sorted(df["etapa"].dropna().unique())
    for i, etapa in enumerate(etapas_unicas[:3]):
        if i >= len(limites) - 1:
            break
        ax.axvspan(limites[i], limites[i + 1],
                   alpha=0.06, color=CORES_ETAPA.get(etapa, "gray"), zorder=0)


def marcar_transicoes(ax, transicoes):
    for t in transicoes:
        ax.axvline(t, color="gray", linestyle=":", linewidth=1.0, alpha=0.7)


# ── Carregar dados ─────────────────────────────────────────────────────────────
df_orig = carregar_ensaio(CSV_ORIGINAL)
df_final = carregar_ensaio(CSV_FINAL)

trans_orig = transicoes_etapas(df_orig)
trans_final = transicoes_etapas(df_final)

# ── Figura: 3 linhas x 2 colunas (origem | final) ──────────────────────────────
fig, axes = plt.subplots(3, 2, figsize=(16, 11), sharex="col")
fig.suptitle(
    "Comparação dos ensaios FT — Esquerda: dados_ensaio_ft.csv  |  Direita: dados_ensaio_ft_final.csv",
    fontsize=12, fontweight="bold", y=0.98,
)

# ── Coluna 1: Ensaio original (com perfil 40→50→35 °C) ─────────────────────────
for ax, trans in zip(axes[:, 0], [trans_orig] * 3):
    marcar_transicoes(ax, trans)
sombrear_etapas(axes[0, 0], df_orig, trans_orig)
sombrear_etapas(axes[1, 0], df_orig, trans_orig)
sombrear_etapas(axes[2, 0], df_orig, trans_orig)

# Temperatura
ax = axes[0, 0]
ax.plot(df_orig["tempo_min"], df_orig["temperatura"],
        color="#d62728", linewidth=0.9, label="Temperatura medida", zorder=3)
if "sp_temperatura" in df_orig.columns:
    ax.step(df_orig["tempo_min"], df_orig["sp_temperatura"],
            color="black", linewidth=1.2, linestyle="--", where="post",
            label="Setpoint (perfil)", zorder=4)
    for sp, t in zip([40, 50, 35], [0.0] + trans_orig[:2]):
        ax.annotate(f"SP = {sp} °C", xy=(t, sp), xytext=(t + 0.4, sp + 0.8),
                    fontsize=8, color="black",
                    arrowprops=dict(arrowstyle="->", color="black", lw=0.8))
ax.set_ylabel("Temperatura (°C)", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Temperatura — Ensaio original", fontsize=10, loc="left")

# Vazão
ax = axes[1, 0]
ax.plot(df_orig["tempo_min"], df_orig["vazao"],
        color="#1f77b4", linewidth=0.9, label="Vazão medida", zorder=3)
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.8,
           label=f"SP ({SP_VAZAO} L/min)", zorder=4)
m = df_orig["vazao"].mean()
ax.axhline(m, color="#9467bd", linestyle="-.", linewidth=1.2, alpha=0.9,
           label=f"Média ({m:.2f} L/min)", zorder=4)
ax.set_ylabel("Vazão (L/min)", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Vazão — Ensaio original", fontsize=10, loc="left")

# Duty cycles
ax = axes[2, 0]
ax.plot(df_orig["tempo_min"], df_orig["dc_cooler"],
        color="#2ca02c", linewidth=0.9, label="DC Cooler", zorder=3)
ax.plot(df_orig["tempo_min"], df_orig["dc_resistencia"],
        color="#ff7f0e", linewidth=0.9, label="DC Resistência", zorder=3)
ax.set_ylabel("Duty Cycle (%)", fontsize=10)
ax.set_xlabel("Tempo (min)", fontsize=10)
ax.set_ylim(-2, 105)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Sinais de Controle — Ensaio original", fontsize=10, loc="left")

# ── Coluna 2: Ensaio final (sem perfil de setpoint/etapas) ─────────────────────
for ax in axes[:, 1]:
    marcar_transicoes(ax, trans_final)
sombrear_etapas(axes[0, 1], df_final, trans_final)
sombrear_etapas(axes[1, 1], df_final, trans_final)
sombrear_etapas(axes[2, 1], df_final, trans_final)

# Temperatura
ax = axes[0, 1]
ax.plot(df_final["tempo_min"], df_final["temperatura"],
        color="#d62728", linewidth=0.9, label="Temperatura medida", zorder=3)
ax.set_ylabel("Temperatura (°C)", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Temperatura — Ensaio final", fontsize=10, loc="left")

# Vazão
ax = axes[1, 1]
ax.plot(df_final["tempo_min"], df_final["vazao"],
        color="#1f77b4", linewidth=0.9, label="Vazão medida", zorder=3)
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", linewidth=1.2, alpha=0.8,
           label=f"SP ({SP_VAZAO} L/min)", zorder=4)
m = df_final["vazao"].mean()
ax.axhline(m, color="#9467bd", linestyle="-.", linewidth=1.2, alpha=0.9,
           label=f"Média ({m:.2f} L/min)", zorder=4)
ax.set_ylabel("Vazão (L/min)", fontsize=10)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Vazão — Ensaio final", fontsize=10, loc="left")

# Duty cycles
ax = axes[2, 1]
ax.plot(df_final["tempo_min"], df_final["dc_cooler"],
        color="#2ca02c", linewidth=0.9, label="DC Cooler", zorder=3)
ax.plot(df_final["tempo_min"], df_final["dc_resistencia"],
        color="#ff7f0e", linewidth=0.9, label="DC Resistência", zorder=3)
ax.set_ylabel("Duty Cycle (%)", fontsize=10)
ax.set_xlabel("Tempo (min)", fontsize=10)
ax.set_ylim(-2, 105)
ax.legend(loc="upper right", fontsize=8)
ax.grid(True, alpha=0.3)
ax.set_title("Sinais de Controle — Ensaio final", fontsize=10, loc="left")

# Legenda global (só para o ensaio original que tem etapas)
if trans_orig:
    patches = [
        mpatches.Patch(color=CORES_ETAPA[1], alpha=0.4, label="Etapa 1 — SP 40 °C"),
        mpatches.Patch(color=CORES_ETAPA[2], alpha=0.4, label="Etapa 2 — SP 50 °C"),
        mpatches.Patch(color=CORES_ETAPA[3], alpha=0.4, label="Etapa 3 — SP 35 °C"),
        Line2D([0], [0], color="gray", linestyle=":", linewidth=1.2, label="Transição"),
    ]
    fig.legend(handles=patches, loc="lower center", ncol=4, fontsize=8,
               framealpha=0.9, bbox_to_anchor=(0.5, 0.01))

plt.tight_layout(rect=[0, 0.04, 1, 0.96])
plt.savefig("grafico_comparacao_ensaios_ft.png", dpi=150, bbox_inches="tight")
plt.show()

print(f"Original: {len(df_orig)} amostras, {df_orig['tempo_min'].iloc[-1]:.1f} min")
print(f"Final:    {len(df_final)} amostras, {df_final['tempo_min'].iloc[-1]:.1f} min")
print("Gráfico salvo em grafico_comparacao_ensaios_ft.png")
