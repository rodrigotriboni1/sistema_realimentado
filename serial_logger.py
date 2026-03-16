"""
Captura dados do sistema realimentado via Serial (ESP32) a cada 2 segundos e grava em CSV.
"""

import serial
import csv
import re
from datetime import datetime
from typing import Optional
import time
from pathlib import Path

# Configurações
PORTA_SERIAL = "COM7"
BAUD_RATE = 115200
OUTPUT_DIR = Path("data/raw")
ARQUIVO_CSV = OUTPUT_DIR / "dados_ensaio_ft.csv"


def extrair_dados(linha: str) -> Optional[dict]:
    """
    Extrai dados da linha serial.
    Formato: Temp: 25.50 C | SP: 40.0 C | Etapa: 1 | Vazao: 1.20 L/min | DC_Cooler: 50% | DC_Resist: 30% | Resistencia: ON
    """
    padrao = (
        r"Temp:\s*([-\d.]+)\s*C\s*\|\s*"
        r"SP:\s*([-\d.]+)\s*C\s*\|\s*"
        r"Etapa:\s*(\d+)\s*\|\s*"
        r"Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*"
        r"DC_Cooler:\s*(\d+)%\s*\|\s*"
        r"DC_Resist:\s*(\d+)%\s*\|\s*"
        r"Resistencia:\s*(ON|OFF)"
    )
    match = re.search(padrao, linha)
    if match:
        return {
            "temperatura": float(match.group(1)),
            "sp_temperatura": float(match.group(2)),
            "etapa": int(match.group(3)),
            "vazao": float(match.group(4)),
            "dc_cooler": int(match.group(5)),
            "dc_resistencia": int(match.group(6)),
            "resistencia": match.group(7),
        }
    return None


def main():
    print(f"Conectando à porta {PORTA_SERIAL} ({BAUD_RATE} baud)...")

    try:
        ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
        print("Conectado! Aguardando dados (a cada ~2s)...")
    except serial.SerialException as e:
        print(f"Erro ao abrir porta serial: {e}")
        print("Verifique a porta e se o ESP32 está conectado.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Cria arquivo CSV com cabeçalho
    arquivo_existe = False
    try:
        with open(ARQUIVO_CSV, "r") as f:
            arquivo_existe = True
    except FileNotFoundError:
        pass

    try:
        with open(ARQUIVO_CSV, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            if not arquivo_existe:
                writer.writerow(["timestamp", "temperatura_C", "sp_temperatura_C", "etapa", "vazao_L_min", "dc_cooler_%", "dc_resistencia_%", "resistencia"])

            while True:
                if ser.in_waiting:
                    linha = ser.readline().decode("utf-8", errors="ignore").strip()
                    dados = extrair_dados(linha)
                    if dados:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        writer.writerow([
                            timestamp,
                            dados["temperatura"],
                            dados["sp_temperatura"],
                            dados["etapa"],
                            dados["vazao"],
                            dados["dc_cooler"],
                            dados["dc_resistencia"],
                            dados["resistencia"],
                        ])
                        csvfile.flush()
                        print(
                            f"[{timestamp}] Temp: {dados['temperatura']:.2f}°C | "
                            f"SP: {dados['sp_temperatura']:.1f}°C | "
                            f"Etapa: {dados['etapa']} | "
                            f"Vazao: {dados['vazao']:.2f} L/min | "
                            f"Cooler: {dados['dc_cooler']}% | "
                            f"Resist: {dados['dc_resistencia']}%"
                        )

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
