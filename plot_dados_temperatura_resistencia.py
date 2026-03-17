"""
Gera grafico para data/raw/dados_temperatura_resistencia.csv.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

CSV_DEFAULT = Path("data/raw/dados_temperatura_resistencia.csv")
PLOTS_DIR = Path("plots")

csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_DEFAULT

df = pd.read_csv(csv_path)
df = df.rename(
    columns={
        "temperatura_C": "temperatura",
        "vazao_L_min": "vazao",
        "cooler_%": "cooler",
    }
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["resistencia_on"] = (df["resistencia"].astype(str).str.upper() == "ON").astype(int) * 100
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
fig.suptitle("Ensaio de Temperatura com Resistencia", fontsize=13, fontweight="bold")

ax = axes[0]
ax.plot(df["tempo_min"], df["temperatura"], color="#d62728", linewidth=0.9, label="Temperatura")
ax.set_ylabel("Temperatura (C)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(df["tempo_min"], df["resistencia_on"], color="#ff7f0e", linewidth=0.9, label="Resistencia ON/OFF")
ax.set_ylabel("Resistencia (%)")
ax.set_ylim(-2, 105)
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

ax = axes[2]
ax.plot(df["tempo_min"], df["cooler"], color="#2ca02c", linewidth=0.9, label="Cooler (%)")
ax.set_ylabel("Cooler (%)")
ax.set_ylim(-2, 105)
ax.set_xlabel("Tempo (min)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

plt.tight_layout()
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
output_path = PLOTS_DIR / "grafico_dados_temperatura_resistencia.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
plt.show()
print(f"Grafico salvo em {output_path} ({len(df)} amostras)")
