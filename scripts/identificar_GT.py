#!/usr/bin/env python3
"""
Identificação da função de transferência G_T(s): temperatura de saída / tensão (PWM) na resistência.

Uso:
  1. No Serial Monitor, envie "ENSAIO" com cooler desligado e caixa em temperatura ambiente.
  2. Salve as linhas no formato "time_ms,temp_C" em um arquivo CSV (ex: dados_ensaio.csv).
  3. Execute: python identificar_GT.py dados_ensaio.csv

  Ou cole os dados no stdin (apenas as linhas numéricas):
     python identificar_GT.py < dados_ensaio.csv
     python identificar_GT.py  (e cole time_ms,temp_C linha a linha, Ctrl+Z Enter no Windows)

O script subtrai a temperatura ambiente (primeira amostra), ajusta um sistema de 1ª ordem
  delta_T(t) = K * (1 - exp(-t/tau))
e retorna G_T(s) = K / (tau*s + 1) e o valor em regime permanente (setpoint máximo).
"""

import sys
import re
import numpy as np
from scipy.optimize import curve_fit

# Período de amostragem usado no firmware (s)
TS = 2.0


def first_order_step(t, K, tau):
    """Resposta ao degrau de 1ª ordem: delta_T(t) = K * (1 - exp(-t/tau))."""
    return K * (1.0 - np.exp(-t / tau))


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    # Filtrar linhas que são "time_ms,temp_C" (números)
    data = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("ENSAIO") or line.startswith("REGIME") or line.startswith("Use") or line == "time_ms,temp_C":
            continue
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                t_ms = float(parts[0])
                T = float(parts[1])
                data.append((t_ms, T))
            except ValueError:
                continue

    if len(data) < 5:
        print("Dados insuficientes. Forneça um CSV com colunas time_ms,temp_C (uma amostra por período de amostragem).")
        sys.exit(1)

    t_ms = np.array([d[0] for d in data])
    temp_C = np.array([d[1] for d in data])
    t_s = t_ms / 1000.0

    # Subtrair temperatura ambiente (condição inicial) conforme enunciado
    T_ambiente = temp_C[0]
    delta_T = temp_C - T_ambiente

    # Ajuste: delta_T(t) = K * (1 - exp(-t/tau))
    # Evitar tau=0 ou negativo
    p0 = (float(np.max(delta_T)), (t_s[-1] - t_s[0]) / 3.0)
    bounds = ([0.0, 0.1], [np.max(delta_T) * 2, 1e6])
    try:
        popt, _ = curve_fit(first_order_step, t_s, delta_T, p0=p0, bounds=bounds, maxfev=5000)
        K, tau = popt
    except Exception as e:
        print("Ajuste numérico falhou:", e)
        K = float(np.max(delta_T))
        tau = (t_s[-1] - t_s[0]) / 3.0
        print("Usando estimativa: K =", K, "tau =", tau)

    # Temperatura em regime permanente (antes já era temp_C final; com modelo: T_ambiente + K)
    T_regime_modelo = T_ambiente + K
    T_regime_medido = float(temp_C[-1])

    print()
    print("=== Identificação G_T(s) ===")
    print("Temperatura ambiente (1ª amostra): {:.2f} °C".format(T_ambiente))
    print("Temperatura em regime permanente (medida): {:.2f} °C".format(T_regime_medido))
    print("Temperatura em regime permanente (modelo T_amb + K): {:.2f} °C".format(T_regime_modelo))
    print()
    print("Parâmetros do modelo de 1ª ordem (delta_T = K*(1 - exp(-t/tau))):")
    print("  K  = {:.2f} °C (ganho em regime para entrada u=1)".format(K))
    print("  tau = {:.2f} s (constante de tempo)".format(tau))
    print()
    print("Função de transferência (temperatura de saída / tensão na resistência):")
    print("  G_T(s) = K / (tau*s + 1)")
    print("  G_T(s) = {:.2f} / ({:.2f}*s + 1)".format(K, tau))
    print()
    print("Setpoint máximo permitido (para o controlador): {:.2f} °C".format(T_regime_medido))
    print("O sistema não atinge temperaturas acima desse valor com 100% de PWM na resistência.")
    print()

    # Opcional: salvar curva ajustada para conferência
    delta_T_ajustado = first_order_step(t_s, K, tau)
    if len(sys.argv) > 2 and sys.argv[2] == "--save":
        out = sys.argv[1].replace(".csv", "_ajustado.csv") if ".csv" in sys.argv[1] else "ajustado.csv"
        with open(out, "w", encoding="utf-8") as f:
            f.write("time_s,delta_T_medido,delta_T_ajustado\n")
            for i in range(len(t_s)):
                f.write("{:.2f},{:.4f},{:.4f}\n".format(t_s[i], delta_T[i], delta_T_ajustado[i]))
        print("Curva ajustada salva em:", out)


if __name__ == "__main__":
    main()
