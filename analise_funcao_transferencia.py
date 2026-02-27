"""
Processa dados do ensaio térmico e determina a função de transferência G(s).
- Subtrai a temperatura inicial (condição de referência)
- Identifica modelo FOPDT: G(s) = K * exp(-L*s) / (tau*s + 1)
- Entrada: PWM cooler (step 0->100%), Saída: variação de temperatura
"""

import csv
import sys
from datetime import datetime
from typing import List, Tuple, Optional

import numpy as np
from scipy.optimize import curve_fit


def carregar_csv(arquivo: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Carrega CSV e retorna tempo(s), temperatura, cooler, resistencia."""
    tempo = []
    temp = []
    cooler = []
    resistencia = []

    with open(arquivo, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        t0 = None
        for row in reader:
            ts = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
            if t0 is None:
                t0 = ts
            tempo.append((ts - t0).total_seconds())
            temp.append(float(row["temperatura_C"]))
            cooler.append(int(row["cooler_%"]))
            resistencia.append(1 if row["resistencia"] == "ON" else 0)

    return np.array(tempo), np.array(temp), np.array(cooler), np.array(resistencia)


def encontrar_step_cooler(cooler: np.ndarray) -> Optional[int]:
    """Retorna o índice onde cooler passa de 0 para 100."""
    for i in range(1, len(cooler)):
        if cooler[i - 1] == 0 and cooler[i] == 100:
            return i
    return None


def modelo_fopdt(t: np.ndarray, K: float, tau: float, L: float) -> np.ndarray:
    """Resposta ao degrau: y(t) = K * (1 - exp(-(t-L)/tau)) para t > L, else 0."""
    y = np.zeros_like(t)
    mask = t > L
    y[mask] = K * (1 - np.exp(-(t[mask] - L) / tau))
    return y


def identificar_fopdt(t: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """Ajusta modelo FOPDT aos dados. Retorna K, tau, L."""
    # Estimativas iniciais
    y_final = np.mean(y[-10:]) if len(y) >= 10 else y[-1]
    K_est = y_final
    tau_est = (t[-1] - t[0]) / 3 if len(t) > 1 else 10
    L_est = 0

    try:
        popt, _ = curve_fit(
            modelo_fopdt,
            t,
            y,
            p0=[K_est, tau_est, L_est],
            bounds=([-100, 0.1, 0], [100, 1000, 60]),
            maxfev=5000,
        )
        return float(popt[0]), float(popt[1]), float(popt[2])
    except Exception as e:
        print(f"Aviso: Ajuste FOPDT falhou ({e}). Usando estimativas.")
        return K_est, tau_est, L_est


def main():
    args = sys.argv[1:]
    arquivo = "dados_temperatura_resistencia.csv"
    idx_step_manual = None
    i = 0
    while i < len(args):
        if args[i] == "--step-indice" and i + 1 < len(args):
            idx_step_manual = int(args[i + 1])
            i += 2
        else:
            arquivo = args[i]
            i += 1

    print(f"Carregando {arquivo}...")
    tempo, temp, cooler, resistencia = carregar_csv(arquivo)

    if idx_step_manual is not None:
        idx_step = idx_step_manual
        print(f"Usando indice do step informado: {idx_step}")
    else:
        idx_step = encontrar_step_cooler(cooler)
        if idx_step is None:
            print("ERRO: Nao encontrado step do cooler (0 -> 100%).")
            print("Execute o ensaio com main.cpp ou use --step-indice N para indicar manualmente.")
            sys.exit(1)

    # Dados a partir do step
    t = tempo[idx_step:] - tempo[idx_step]
    T = temp[idx_step:]
    T_inicial = temp[idx_step - 1]  # Temperatura logo antes do step
    delta_T = T - T_inicial

    print(f"\n--- Dados do ensaio ---")
    print(f"Temperatura inicial (referencia): {T_inicial:.2f} C")
    print(f"Step do cooler no indice {idx_step} (t=0)")
    print(f"Amostras apos step: {len(t)}")
    print(f"Periodo de amostragem: {t[1]-t[0]:.1f} s" if len(t) > 1 else "")

    # Identificação FOPDT
    K, tau, L = identificar_fopdt(t, delta_T)

    print(f"\n--- Funcao de Transferencia G(s) ---")
    print(f"Modelo FOPDT: G(s) = K * exp(-L*s) / (tau*s + 1)")
    print(f"  K (ganho) = {K:.4f} C/100%  (variacao de temp por unidade de PWM)")
    print(f"  tau (constante de tempo) = {tau:.2f} s")
    print(f"  L (atraso) = {L:.2f} s")
    print(f"\n  G(s) = {K:.4f} * exp(-{L:.2f}*s) / ({tau:.2f}*s + 1)")

    # Salvar dados processados
    saida_csv = "dados_processados_ft.csv"
    with open(saida_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["tempo_s", "delta_T_C", "temperatura_C"])
        for i in range(len(t)):
            writer.writerow([t[i], delta_T[i], T[i]])
    print(f"\nDados processados (delta_T) salvos em {saida_csv}")

    # Plot opcional
    try:
        import matplotlib.pyplot as plt

        y_ajuste = modelo_fopdt(t, K, tau, L)
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.plot(t, delta_T, "b.", label="Dados")
        plt.plot(t, y_ajuste, "r-", label="Modelo FOPDT")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Delta T (C)")
        plt.title("Resposta ao degrau - Temperatura (ref. inicial)")
        plt.legend()
        plt.grid(True)

        plt.subplot(1, 2, 2)
        plt.plot(tempo, temp, "g-", label="Temperatura")
        plt.axvline(tempo[idx_step], color="r", linestyle="--", label="Step cooler")
        plt.xlabel("Tempo (s)")
        plt.ylabel("Temperatura (C)")
        plt.title("Ensaio completo")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig("resposta_degrau_ft.png", dpi=150)
        print("Grafico salvo em resposta_degrau_ft.png")
    except ImportError:
        print("(Instale matplotlib para gerar graficos: pip install matplotlib)")


if __name__ == "__main__":
    main()
