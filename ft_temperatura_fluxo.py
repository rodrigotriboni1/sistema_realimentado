"""
Gera funções de transferência separadas:
- G_T(s): Resistência PWM -> Temperatura (dados_temperatura_resistencia.csv)
- G_F(s): Cooler PWM -> Fluxo (dados_fluxo.csv)
"""

import csv
from datetime import datetime
from typing import Tuple

import numpy as np
from scipy.optimize import curve_fit


def carregar_csv(arquivo: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Carrega CSV e retorna tempo(s), temperatura, vazao, cooler, resistencia."""
    tempo, temp, vazao, cooler, resistencia = [], [], [], [], []

    with open(arquivo, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        t0 = None
        for row in reader:
            ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
            if t0 is None:
                t0 = ts
            tempo.append((ts - t0).total_seconds())
            temp.append(float(row["temperatura_C"]))
            vazao.append(float(row["vazao_L_min"]))
            cooler.append(int(row["cooler_%"]))
            resistencia.append(1 if row["resistencia"] == "ON" else 0)

    return (
        np.array(tempo),
        np.array(temp),
        np.array(vazao),
        np.array(cooler),
        np.array(resistencia),
    )


def modelo_fopdt(t: np.ndarray, K: float, tau: float, L: float) -> np.ndarray:
    """Resposta ao degrau: y(t) = K * (1 - exp(-(t-L)/tau)) para t > L, else 0."""
    y = np.zeros_like(t)
    mask = t > L
    y[mask] = K * (1 - np.exp(-(t[mask] - L) / tau))
    return y


def identificar_fopdt(t: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """Ajusta modelo FOPDT. Retorna K, tau, L."""
    y_final = np.mean(y[-20:]) if len(y) >= 20 else y[-1]
    K_est = y_final
    tau_est = (t[-1] - t[0]) / 3 if len(t) > 1 else 10
    L_est = 0

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
    except Exception as e:
        print(f"  Aviso: Ajuste falhou ({e}). Usando estimativas.")
        return K_est, tau_est, L_est


def ft_temperatura(arquivo: str = "dados_temperatura_resistencia.csv"):
    """
    G_T(s): Resistência PWM -> Temperatura
    Entrada: step resistência 0->100% em t=0
    Saída: delta_T = T(t) - T(0)
    """
    print("=" * 60)
    print("G_T(s): Função de Transferência TEMPERATURA")
    print("Entrada: Resistência PWM | Saída: Temperatura")
    print("=" * 60)

    tempo, temp, vazao, cooler, resistencia = carregar_csv(arquivo)
    t = tempo
    T0 = temp[0]
    y = temp - T0

    print(f"Arquivo: {arquivo}")
    print(f"Temperatura inicial (ref): {T0:.2f} C")
    print(f"Amostras: {len(t)} | Período: {t[1]-t[0]:.1f} s")
    print(f"Variação total: {y[-1]:.2f} C")

    K, tau, L = identificar_fopdt(t, y)

    print(f"\nModelo FOPDT: G_T(s) = K * exp(-L*s) / (tau*s + 1)")
    print(f"  K = {K:.4f} C/100%  (ganho: °C por unidade de PWM resistência)")
    print(f"  tau = {tau:.2f} s")
    print(f"  L = {L:.2f} s")
    print(f"\n  G_T(s) = {K:.4f} * exp(-{L:.2f}*s) / ({tau:.2f}*s + 1)")

    # Salvar e plotar
    with open("dados_ft_temperatura.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tempo_s", "delta_T_C", "temperatura_C"])
        for i in range(len(t)):
            w.writerow([t[i], y[i], temp[i]])
    print(f"\nDados salvos em dados_ft_temperatura.csv")

    return t, y, K, tau, L, "temperatura"


def ft_fluxo(arquivo: str = "dados_fluxo.csv"):
    """
    G_F(s): Cooler PWM -> Fluxo (vazão)
    Entrada: step cooler 0->100% em t=0
    Saída: delta_fluxo = vazao(t) - vazao(0)
    """
    print("\n" + "=" * 60)
    print("G_F(s): Função de Transferência FLUXO")
    print("Entrada: Cooler PWM | Saída: Vazão (L/min)")
    print("=" * 60)

    tempo, temp, vazao, cooler, resistencia = carregar_csv(arquivo)
    t = tempo
    Q0 = vazao[0]
    y = vazao - Q0

    print(f"Arquivo: {arquivo}")
    print(f"Vazão inicial (ref): {Q0:.2f} L/min")
    print(f"Amostras: {len(t)} | Período: {t[1]-t[0]:.1f} s")
    print(f"Variação total: {y[-1]:.2f} L/min")

    K, tau, L = identificar_fopdt(t, y)

    print(f"\nModelo FOPDT: G_F(s) = K * exp(-L*s) / (tau*s + 1)")
    print(f"  K = {K:.4f} (L/min)/100%  (ganho: vazão por unidade de PWM cooler)")
    print(f"  tau = {tau:.2f} s")
    print(f"  L = {L:.2f} s")
    print(f"\n  G_F(s) = {K:.4f} * exp(-{L:.2f}*s) / ({tau:.2f}*s + 1)")

    with open("dados_ft_fluxo.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tempo_s", "delta_vazao_L_min", "vazao_L_min"])
        for i in range(len(t)):
            w.writerow([t[i], y[i], vazao[i]])
    print(f"\nDados salvos em dados_ft_fluxo.csv")

    return t, y, K, tau, L, "fluxo"


def main():
    # FT Temperatura (resistência -> temperatura)
    t1, y1, K1, tau1, L1, _ = ft_temperatura("dados_temperatura_resistencia.csv")

    # FT Fluxo (cooler -> vazão)
    t2, y2, K2, tau2, L2, _ = ft_fluxo("dados_fluxo.csv")

    # Gráficos
    try:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        # Temperatura - dados e ajuste
        y1_ajuste = modelo_fopdt(t1, K1, tau1, L1)
        axes[0, 0].plot(t1, y1, "b.", label="Dados", markersize=3)
        axes[0, 0].plot(t1, y1_ajuste, "r-", label="FOPDT", linewidth=2)
        axes[0, 0].set_xlabel("Tempo (s)")
        axes[0, 0].set_ylabel("Delta T (°C)")
        axes[0, 0].set_title("G_T(s): Resistência → Temperatura")
        axes[0, 0].legend()
        axes[0, 0].grid(True)

        # Temperatura - sinal completo
        tempo1, temp1, _, _, _ = carregar_csv("dados_temperatura_resistencia.csv")
        axes[0, 1].plot(tempo1, temp1, "g-")
        axes[0, 1].set_xlabel("Tempo (s)")
        axes[0, 1].set_ylabel("Temperatura (°C)")
        axes[0, 1].set_title("Temperatura (ensaio resistência)")
        axes[0, 1].grid(True)

        # Fluxo - dados e ajuste
        y2_ajuste = modelo_fopdt(t2, K2, tau2, L2)
        axes[1, 0].plot(t2, y2, "b.", label="Dados", markersize=3)
        axes[1, 0].plot(t2, y2_ajuste, "r-", label="FOPDT", linewidth=2)
        axes[1, 0].set_xlabel("Tempo (s)")
        axes[1, 0].set_ylabel("Delta Vazão (L/min)")
        axes[1, 0].set_title("G_F(s): Cooler → Fluxo")
        axes[1, 0].legend()
        axes[1, 0].grid(True)

        # Fluxo - sinal completo
        tempo2, _, vazao2, _, _ = carregar_csv("dados_fluxo.csv")
        axes[1, 1].plot(tempo2, vazao2, "g-")
        axes[1, 1].set_xlabel("Tempo (s)")
        axes[1, 1].set_ylabel("Vazão (L/min)")
        axes[1, 1].set_title("Fluxo (ensaio cooler)")
        axes[1, 1].grid(True)

        plt.tight_layout()
        plt.savefig("ft_temperatura_fluxo.png", dpi=150)
        print("\nGráfico salvo em ft_temperatura_fluxo.png")
    except ImportError:
        print("\n(Instale matplotlib para gráficos: pip install matplotlib)")


if __name__ == "__main__":
    main()
