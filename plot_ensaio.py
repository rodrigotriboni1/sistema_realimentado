"""
Gera gráficos do ensaio do sistema realimentado a partir do CSV.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV_PATH = "dados_ensaio_ft.csv"

SP_TEMPERATURA = 40.0  # °C
SP_VAZAO = 1.0         # L/min

df = pd.read_csv(
    CSV_PATH,
    header=None,
    skiprows=1,
    names=["timestamp", "temperatura", "vazao", "dc_cooler", "dc_resistencia", "resistencia"],
)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df["tempo_s"] = (df["timestamp"] - df["timestamp"].iloc[0]).dt.total_seconds()

fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
fig.suptitle("Ensaio do Sistema Realimentado — PID Discreto (ZOH, Ts = 2s)", fontsize=14, fontweight="bold")

# --- Temperatura ---
ax = axes[0]
ax.plot(df["tempo_s"], df["temperatura"], color="#d62728", linewidth=0.8, label="Temperatura")
ax.axhline(SP_TEMPERATURA, color="#d62728", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_TEMPERATURA} °C)")
ax.set_ylabel("Temperatura (°C)")
ax.legend(loc="lower right")
ax.grid(True, alpha=0.3)

# --- Vazão ---
ax = axes[1]
ax.plot(df["tempo_s"], df["vazao"], color="#1f77b4", linewidth=0.8, label="Vazão")
ax.axhline(SP_VAZAO, color="#1f77b4", linestyle="--", alpha=0.6, label=f"Setpoint ({SP_VAZAO} L/min)")
ax.set_ylabel("Vazão (L/min)")
ax.legend(loc="upper right")
ax.grid(True, alpha=0.3)

# --- Duty Cycles ---
ax = axes[2]
ax.plot(df["tempo_s"], df["dc_cooler"], color="#2ca02c", linewidth=0.8, label="DC Cooler (PID Vazão)")
ax.plot(df["tempo_s"], df["dc_resistencia"], color="#ff7f0e", linewidth=0.8, label="DC Resistência (PID Temp)")
ax.set_ylabel("Duty Cycle (%)")
ax.set_xlabel("Tempo (s)")
ax.legend(loc="center right")
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("grafico_ensaio.png", dpi=150)
plt.show()
print("Gráfico salvo em grafico_ensaio.png")
