"""
Captura dados do experimento PID novo via serial e grava em CSV.

Formato esperado (main.cpp):
Temp: 38.50 C | SP_Temp: 40.0 C | Fase: AQUECENDO | Estab: 2/15 |
Vazao: 0.00 L/min | SP_Vazao: 0.0 | DC_Cooler: 0% | DC_Resist: 75% | Resistencia: ON
"""

import csv
import re
import time
from datetime import datetime
from typing import Optional

import serial

# Configuracoes
PORTA_SERIAL = "COM7"
BAUD_RATE = 115200
ARQUIVO_CSV = "dados_ensaio_pid_novo.csv"


def extrair_pid_novo(linha: str) -> Optional[dict]:
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
    m = re.search(padrao, linha)
    if not m:
        return None

    return {
        "temperatura": float(m.group(1)),
        "sp_temperatura": float(m.group(2)),
        "fase": m.group(3),
        "estab_contagem": int(m.group(4)),
        "estab_alvo": int(m.group(5)),
        "vazao": float(m.group(6)),
        "sp_vazao": float(m.group(7)),
        "dc_cooler": int(m.group(8)),
        "dc_resistencia": int(m.group(9)),
        "resistencia": m.group(10),
    }


def main() -> None:
    print("Modo: PID novo (variacao de fase AQUECENDO -> COOLER_ON -> ESTABILIZADO)")
    print(f"Porta: {PORTA_SERIAL} | Baud: {BAUD_RATE}")
    print(f"Arquivo de saida: {ARQUIVO_CSV}\n")

    try:
        ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
        print("Conectado! Aguardando dados...\n")
    except serial.SerialException as e:
        print(f"Erro ao abrir porta serial: {e}")
        return

    cabecalho = [
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

    arquivo_existe = False
    try:
        with open(ARQUIVO_CSV, "r", encoding="utf-8"):
            arquivo_existe = True
    except FileNotFoundError:
        pass

    amostras = 0
    fase_anterior = None

    try:
        with open(ARQUIVO_CSV, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if not arquivo_existe:
                writer.writerow(cabecalho)

            while True:
                if ser.in_waiting:
                    linha = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not linha:
                        continue

                    if linha.startswith(">>>"):
                        print(f"\n{'=' * 60}")
                        print(f"  {linha[3:].strip()}")
                        print(f"{'=' * 60}\n")
                        continue

                    dados = extrair_pid_novo(linha)
                    if not dados:
                        continue

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    amostras += 1

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

                    if dados["fase"] != fase_anterior:
                        print(f"\n--- Fase: {dados['fase']} ---")
                        fase_anterior = dados["fase"]

                    n = dados["estab_contagem"]
                    alvo = dados["estab_alvo"]
                    barra = "#" * n + "." * max(0, alvo - n)
                    print(
                        f"[{timestamp}] #{amostras:4d} | "
                        f"Temp: {dados['temperatura']:6.2f} C | "
                        f"SP_T: {dados['sp_temperatura']:.1f} C | "
                        f"Fase: {dados['fase']:<12} | "
                        f"Estab: [{barra}] {n}/{alvo} | "
                        f"Vazao: {dados['vazao']:.2f} L/min | "
                        f"SP_F: {dados['sp_vazao']:.1f} | "
                        f"DC_C: {dados['dc_cooler']:3d}% | "
                        f"DC_R: {dados['dc_resistencia']:3d}%"
                    )

                time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\nEncerrado. {amostras} amostras gravadas em {ARQUIVO_CSV}")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
