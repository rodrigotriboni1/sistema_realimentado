"""
Gera grafico para data/raw/dados_ensaio_ft_final.csv.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

CSV_DEFAULT = Path("data/raw/dados_ensaio_ft_final.csv")
PLOTS_DIR = Path("plots")
SP_TEMPERATURA = 40.0
SP_VAZAO = 1.0

csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_DEFAULT

df = pd.read_csv(csv_path)
df = df.rename(
    columns={
        "temperatura_C": "temperatura",
        "vazao_L_min": "vazao",
        "dc_cooler_%": "dc_cooler",
        "dc_resistencia_%": "dc_resistencia",
    }
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
fig.suptitle("Ensaio FT Final", fontsize=13, fontweight="bold")

ax = axes[0]
ax.plot(df["tempo_min"], df["temperatura"], color="#d62728", linewidth=0.9, label="Temperatura")
ax.axhline(SP_TEMPERATURA, color="#d62728", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_TEMPERATURA} C)")
ax.set_ylabel("Temperatura (C)")
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)

ax = axes[1]
ax.plot(df["tempo_min"], df["vazao"], color="#1f77b4", linewidth=0.9, label="Vazao")
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_VAZAO} L/min)")
ax.set_ylabel("Vazao (L/min)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

ax = axes[2]
ax.plot(df["tempo_min"], df["dc_cooler"], color="#2ca02c", linewidth=0.9, label="DC Cooler")
ax.plot(df["tempo_min"], df["dc_resistencia"], color="#ff7f0e", linewidth=0.9, label="DC Resistencia")
ax.set_ylabel("Duty Cycle (%)")
ax.set_xlabel("Tempo (min)")
ax.set_ylim(-2, 105)
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

plt.tight_layout()
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
output_path = PLOTS_DIR / "grafico_dados_ensaio_ft_final.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
plt.show()
print(f"Grafico salvo em {output_path} ({len(df)} amostras)")
