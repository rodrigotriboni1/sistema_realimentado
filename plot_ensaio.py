"""
Gera gráficos do ensaio do sistema realimentado a partir do CSV.
"""

import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

DATA_RAW_DIR = Path("data/raw")
PLOTS_DIR = Path("plots")
DEFAULT_CSV = DATA_RAW_DIR / "dados_ensaio_ft.csv"
LEGACY_CSV = Path("dados_ensaio_ft.csv")

if len(sys.argv) > 1:
    CSV_PATH = Path(sys.argv[1])
else:
    CSV_PATH = DEFAULT_CSV if DEFAULT_CSV.exists() else LEGACY_CSV

SP_TEMPERATURA = 40.0
SP_VAZAO = 1.0

df = pd.read_csv(CSV_PATH)
df.columns = ["timestamp", "temperatura", "vazao", "dc_cooler", "dc_resistencia", "resistencia"]
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_min"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds() / 60.0

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
fig.suptitle("Ensaio — PID Discreto (ZOH) | Vazão Ts=0.2s | Temp Ts=2s", fontsize=13, fontweight="bold")

# --- Temperatura ---
ax = axes[0]
ax.plot(df["tempo_min"], df["temperatura"], color="#d62728", linewidth=0.8, label="Temperatura")
ax.axhline(SP_TEMPERATURA, color="#d62728", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_TEMPERATURA} °C)")
ax.set_ylabel("Temperatura (°C)")
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)

# --- Vazão ---
ax = axes[1]
ax.plot(df["tempo_min"], df["vazao"], color="#1f77b4", linewidth=0.8, label="Vazão")
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_VAZAO} L/min)")
ax.set_ylabel("Vazão (L/min)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

# --- Duty Cycles ---
ax = axes[2]
ax.plot(df["tempo_min"], df["dc_cooler"], color="#2ca02c", linewidth=0.8, label="DC Cooler (PID Vazão)")
ax.plot(df["tempo_min"], df["dc_resistencia"], color="#ff7f0e", linewidth=0.8, label="DC Resistência (PID Temp)")
ax.set_ylabel("Duty Cycle (%)")
ax.set_xlabel("Tempo (min)")
ax.legend(loc="center right")
ax.grid(True, alpha=0.3)

plt.tight_layout()
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
output_path = PLOTS_DIR / "grafico_ensaio.png"
plt.savefig(output_path, dpi=150)
plt.show()
print(f"Gráfico salvo em {output_path} ({len(df)} amostras)")
