#!/usr/bin/env python3
"""
Identificação da função de transferência G_F(s): vazão de saída / PWM do cooler.

Procedimento:
  1. Com o cooler desligado (PWM = 0%), envie "ENSAIO_GF" pelo Serial Monitor.
  2. O firmware aplica um degrau de 100% no cooler e coleta amostras de vazão até o regime permanente.
  3. Salve as linhas "time_ms,vazao_L_min" em um CSV (use serial_logger.py --gf).
  4. Execute:
       python identificar_GF.py ensaio_gf_XXXXXXXX.csv
       python identificar_GF.py ensaio_gf_XXXXXXXX.csv --save   # também grava curva ajustada

O script ajusta o modelo de 1ª ordem ao degrau unitário:
    F(t) = K_F * (1 - exp(-t / tau_F))

e retorna:
    G_F(s) = K_F / (tau_F * s + 1)

onde:
    K_F  = ganho estático (L/min para entrada u = 1, ou seja, cooler = 100%)
    tau_F = constante de tempo (s)
"""

import sys
import re
import numpy as np
from scipy.optimize import curve_fit

# Período de amostragem padrão no firmware (s) — usado apenas para diagnóstico
TS_GF = 1.0


def resposta_degrau_1ordem(t, K, tau):
    """F(t) = K * (1 - exp(-t / tau))"""
    return K * (1.0 - np.exp(-t / tau))


def carregar_csv(caminho: str) -> list[tuple[float, float]]:
    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    dados = []
    for linha in linhas:
        linha = linha.strip()
        if not linha or not linha[0].isdigit():
            continue
        partes = linha.split(",")
        if len(partes) >= 2:
            try:
                t_ms = float(partes[0])
                F = float(partes[1])
                dados.append((t_ms, F))
            except ValueError:
                continue
    return dados


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("Uso: python identificar_GF.py <arquivo.csv> [--save]")
        sys.exit(1)

    caminho_csv = sys.argv[1]
    salvar = "--save" in sys.argv

    dados = carregar_csv(caminho_csv)

    if len(dados) < 5:
        print("Dados insuficientes. O CSV deve conter pelo menos 5 linhas time_ms,vazao_L_min.")
        sys.exit(1)

    t_ms = np.array([d[0] for d in dados])
    F_raw = np.array([d[1] for d in dados])
    t_s = t_ms / 1000.0

    # A condição inicial é vazão 0 (cooler estava desligado)
    # Subtrai a média das primeiras 3 amostras para remover possível offset de ruído
    F0 = float(np.mean(F_raw[:3]))
    delta_F = F_raw - F0

    # Estimativa inicial: K = valor máximo, tau = 1/3 do tempo total
    K0 = float(np.max(delta_F))
    tau0 = (t_s[-1] - t_s[0]) / 3.0

    bounds_low = [max(K0 * 0.1, 1e-3), 0.1]
    bounds_high = [K0 * 3.0, 1e5]

    try:
        popt, pcov = curve_fit(
            resposta_degrau_1ordem,
            t_s,
            delta_F,
            p0=[K0, tau0],
            bounds=(bounds_low, bounds_high),
            maxfev=10000,
        )
        K_F, tau_F = popt
        perr = np.sqrt(np.diag(pcov))
        K_F_err, tau_F_err = perr
    except Exception as e:
        print(f"Aviso: ajuste numérico falhou ({e}). Usando estimativa grosseira.")
        K_F, tau_F = K0, tau0
        K_F_err = tau_F_err = float("nan")

    # Métricas de qualidade do ajuste
    delta_F_ajustado = resposta_degrau_1ordem(t_s, K_F, tau_F)
    residuos = delta_F - delta_F_ajustado
    ss_res = float(np.sum(residuos**2))
    ss_tot = float(np.sum((delta_F - np.mean(delta_F)) ** 2))
    R2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    rmse = float(np.sqrt(np.mean(residuos**2)))

    F_regime_medido = float(np.mean(F_raw[-min(10, len(F_raw)):]))
    F_regime_modelo = F0 + K_F

    # Tempo de subida 10%-90% (baseado no modelo)
    t_fino = np.linspace(0, t_s[-1] * 2, 50000)
    y_fino = resposta_degrau_1ordem(t_fino, K_F, tau_F)
    idx_10 = np.argmax(y_fino >= 0.1 * K_F)
    idx_90 = np.argmax(y_fino >= 0.9 * K_F)
    t_subida = float(t_fino[idx_90] - t_fino[idx_10]) if idx_90 > idx_10 else float("nan")
    t_acomodo = 4.0 * tau_F  # critério 2% para sistema de 1ª ordem: ~4τ

    print()
    print("=" * 55)
    print("  Identificação G_F(s) — Resposta ao degrau de vazão")
    print("=" * 55)
    print(f"  Arquivo:              {caminho_csv}")
    print(f"  Amostras:             {len(dados)}")
    print(f"  Duração do ensaio:    {t_s[-1]:.1f} s")
    print()
    print("  --- Condições ---")
    print(f"  Vazão inicial (F0):   {F0:.4f} L/min  (cooler 0%)")
    print(f"  Vazão em regime       {F_regime_medido:.4f} L/min  (cooler 100%, medido)")
    print(f"  Vazão em regime       {F_regime_modelo:.4f} L/min  (cooler 100%, modelo F0 + K_F)")
    print()
    print("  --- Parâmetros do modelo de 1ª ordem ---")
    print(f"  K_F  = {K_F:.4f} ± {K_F_err:.4f}  L/min  (ganho estático para u = 1)")
    print(f"  τ_F  = {tau_F:.3f} ± {tau_F_err:.3f}  s      (constante de tempo)")
    print()
    print("  --- Função de transferência ---")
    print()
    print(f"            {K_F:.4f}")
    print(f"  G_F(s) = ─────────────────")
    print(f"           {tau_F:.3f}·s  +  1")
    print()
    print("  --- Qualidade do ajuste ---")
    print(f"  R²   = {R2:.5f}")
    print(f"  RMSE = {rmse:.5f} L/min")
    print()
    print("  --- Características dinâmicas ---")
    print(f"  Tempo de subida (10%-90%):  {t_subida:.2f} s")
    print(f"  Tempo de acomodação (~2%):  {t_acomodo:.2f} s  (4·τ)")
    print("=" * 55)
    print()

    if salvar:
        out = caminho_csv.replace(".csv", "_ajustado.csv")
        with open(out, "w", encoding="utf-8") as f:
            f.write("time_s,delta_F_medido,delta_F_ajustado\n")
            for i in range(len(t_s)):
                f.write(f"{t_s[i]:.3f},{delta_F[i]:.5f},{delta_F_ajustado[i]:.5f}\n")
        print(f"Curva ajustada salva em: {out}")


if __name__ == "__main__":
    main()
