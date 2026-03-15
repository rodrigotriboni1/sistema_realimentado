"""
Captura dados do sistema realimentado via Serial (ESP32) a cada 2 segundos e grava em CSV.
Firmware: aquecimento ate 40 C -> estabilizacao -> cooler ligado (SP 5 L/min) -> nova estabilizacao.
"""

import serial
import csv
import re
from datetime import datetime
from typing import Optional
import time

# Configurações
PORTA_SERIAL = "COM7"
BAUD_RATE    = 115200
ARQUIVO_CSV  = "dados_ensaio_variacao_sp.csv"


LABEL_FASE = {
    "AQUECENDO":    "Aquecendo ate 40 C",
    "COOLER_ON":    "Cooler ligado (SP 5 L/min)",
    "ESTABILIZADO": "Sistema estabilizado",
}


def extrair_dados(linha: str) -> Optional[dict]:
    """
    Extrai dados da linha serial enviada pelo firmware.

    Formato esperado:
      Temp: 38.50 C | SP_Temp: 40.0 C | Fase: AQUECENDO | Estab: 2/5 |
      Vazao: 0.00 L/min | SP_Vazao: 0.0 |
      DC_Cooler: 0% | DC_Resist: 75% | Resistencia: ON
    """
    padrao = (
        r"Temp:\s*([-\d.]+)\s*C\s*\|\s*"
        r"SP_Temp:\s*([-\d.]+)\s*C\s*\|\s*"
        r"Fase:\s*(\w+)\s*\|\s*"
        r"Estab:\s*(\d+)/(\d+)\s*\|\s*"
        r"Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*"
        r"SP_Vazao:\s*([-\d.]+)\s*\|\s*"
        r"DC_Cooler:\s*(\d+)%\s*\|\s*"
        r"DC_Resist:\s*(\d+)%\s*\|\s*"
        r"Resistencia:\s*(ON|OFF)"
    )
    match = re.search(padrao, linha)
    if match:
        return {
            "temperatura":    float(match.group(1)),
            "sp_temperatura": float(match.group(2)),
            "fase":           match.group(3),
            "estab_contagem": int(match.group(4)),
            "estab_alvo":     int(match.group(5)),
            "vazao":          float(match.group(6)),
            "sp_vazao":       float(match.group(7)),
            "dc_cooler":      int(match.group(8)),
            "dc_resistencia": int(match.group(9)),
            "resistencia":    match.group(10),
        }
    return None


CABECALHO = [
    "timestamp",
    "temperatura_C",
    "sp_temperatura_C",
    "fase",
    "estab_contagem",
    "estab_alvo",
    "vazao_L_min",
    "sp_vazao_L_min",
    "dc_cooler_%",
    "dc_resistencia_%",
    "resistencia",
]


def main():
    print(f"Conectando à porta {PORTA_SERIAL} ({BAUD_RATE} baud)...")
    print(f"Arquivo de saída: {ARQUIVO_CSV}")
    print("Ensaio: aquecimento 40 C -> estabilizacao -> cooler 5 L/min -> nova estabilizacao\n")

    try:
        ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
        print("Conectado! Aguardando dados (a cada ~2 s)...\n")
    except serial.SerialException as e:
        print(f"Erro ao abrir porta serial: {e}")
        print("Verifique a porta e se o ESP32 está conectado.")
        return

    arquivo_existe = False
    try:
        with open(ARQUIVO_CSV, "r"):
            arquivo_existe = True
    except FileNotFoundError:
        pass

    fase_anterior = None

    try:
        with open(ARQUIVO_CSV, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if not arquivo_existe:
                writer.writerow(CABECALHO)

            while True:
                if ser.in_waiting:
                    linha = ser.readline().decode("utf-8", errors="ignore").strip()

                    # Eventos do firmware (linhas que começam com >>>)
                    if linha.startswith(">>>"):
                        print(f"\n{'='*60}")
                        print(f"[EVENTO] {linha[4:].strip()}")
                        print(f"{'='*60}\n")
                        continue

                    dados = extrair_dados(linha)
                    if dados:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        writer.writerow([
                            timestamp,
                            dados["temperatura"],
                            dados["sp_temperatura"],
                            dados["fase"],
                            dados["estab_contagem"],
                            dados["estab_alvo"],
                            dados["vazao"],
                            dados["sp_vazao"],
                            dados["dc_cooler"],
                            dados["dc_resistencia"],
                            dados["resistencia"],
                        ])
                        csvfile.flush()

                        # Cabeçalho de fase ao trocar
                        if dados["fase"] != fase_anterior:
                            descricao = LABEL_FASE.get(dados["fase"], dados["fase"])
                            print(f"\n--- Fase: {descricao} ---")
                            fase_anterior = dados["fase"]

                        # Barra de progresso de estabilização
                        n   = dados["estab_contagem"]
                        alvo = dados["estab_alvo"]
                        barra = "#" * n + "." * max(0, alvo - n)

                        print(
                            f"[{timestamp}] "
                            f"Temp: {dados['temperatura']:6.2f} C | "
                            f"SP: {dados['sp_temperatura']:.1f} C | "
                            f"Estab: [{barra}] {n}/{alvo} | "
                            f"Vazao: {dados['vazao']:.2f} L/min | "
                            f"SP_Vz: {dados['sp_vazao']:.1f} | "
                            f"Cooler: {dados['dc_cooler']:3d}% | "
                            f"Resist: {dados['dc_resistencia']:3d}%"
                        )

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()