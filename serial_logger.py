"""
Captura dados de temperatura via Serial (ESP32) a cada 2 segundos e grava em CSV.
"""

import serial
import csv
import re
from datetime import datetime
from typing import Optional
import time

# Configurações
PORTA_SERIAL = "COM6"
BAUD_RATE = 115200
ARQUIVO_CSV = "dados_temperatura.csv"


def extrair_dados(linha: str) -> Optional[dict]:
    """
    Extrai temperatura, vazão, cooler e resistência da linha serial.
    Formato esperado: Temp: 25.50 C | Vazao: 1.20 L/min | Cooler: 50% | Resistencia: ON
    """
    padrao = r"Temp:\s*([-\d.]+)\s*C\s*\|\s*Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*Cooler:\s*(\d+)%\s*\|\s*Resistencia:\s*(ON|OFF)"
    match = re.search(padrao, linha)
    if match:
        return {
            "temperatura": float(match.group(1)),
            "vazao": float(match.group(2)),
            "cooler": int(match.group(3)),
            "resistencia": match.group(4),
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
                writer.writerow(["timestamp", "temperatura_C", "vazao_L_min", "cooler_%", "resistencia"])

            while True:
                if ser.in_waiting:
                    linha = ser.readline().decode("utf-8", errors="ignore").strip()
                    dados = extrair_dados(linha)
                    if dados:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        writer.writerow([
                            timestamp,
                            dados["temperatura"],
                            dados["vazao"],
                            dados["cooler"],
                            dados["resistencia"],
                        ])
                        csvfile.flush()
                        print(f"[{timestamp}] Temp: {dados['temperatura']:.2f}°C | Salvo em {ARQUIVO_CSV}")

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
