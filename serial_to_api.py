"""
Ponte Serial -> API (Fase 3).
Lê a porta serial (formato do ESP32), parseia cada linha e envia POST /api/sample.
O backend retransmite aos clientes WebSocket.
Configuração: variáveis de ambiente COM_PORT, BACKEND_URL ou argumentos -p / -u.
"""

import argparse
import os
import re
import time
from typing import Optional

import requests
import serial

# Valores padrão (podem ser sobrescritos por env ou CLI)
DEFAULT_PORT = "COM6"
DEFAULT_BAUD = 115200
DEFAULT_BACKEND = "http://127.0.0.1:8000"

# Backoff: atrasos em segundos ao falhar POST (máx. 30s)
BACKOFF_DELAYS = [5, 10, 30]
MAX_BACKOFF = 30


def extrair_dados(linha: str) -> Optional[dict]:
    """
    Extrai temperatura, vazão, cooler e resistência da linha serial.
    Formato: Temp: 25.50 C | Vazao: 1.20 L/min | Cooler: 50% | Resistencia: ON
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


def parse_args():
    parser = argparse.ArgumentParser(description="Ponte Serial -> API. Envia amostras do ESP32 para o backend.")
    parser.add_argument(
        "-p", "--port",
        default=os.environ.get("COM_PORT", DEFAULT_PORT),
        help=f"Porta serial (env: COM_PORT). Padrão: {DEFAULT_PORT}",
    )
    parser.add_argument(
        "-b", "--baud",
        type=int,
        default=int(os.environ.get("COM_BAUD", DEFAULT_BAUD)),
        help=f"Baud rate (env: COM_BAUD). Padrão: {DEFAULT_BAUD}",
    )
    parser.add_argument(
        "-u", "--url",
        default=os.environ.get("BACKEND_URL", DEFAULT_BACKEND),
        help=f"URL base do backend (env: BACKEND_URL). Padrão: {DEFAULT_BACKEND}",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    port = args.port
    baud = args.baud
    backend_url = args.url.rstrip("/")
    url = f"{backend_url}/api/sample"

    print(f"Conectando à porta {port} ({baud} baud)...")
    print(f"Backend: {url}")

    try:
        ser = serial.Serial(port, baud, timeout=1)
        print("Conectado! Enviando amostras para a API...")
    except serial.SerialException as e:
        print(f"Erro ao abrir porta serial: {e}")
        print("Verifique a porta e se o ESP32 está conectado.")
        return

    backoff_idx = 0
    try:
        while True:
            if ser.in_waiting:
                linha = ser.readline().decode("utf-8", errors="ignore").strip()
                dados = extrair_dados(linha)
                if dados:
                    enviado = False
                    while not enviado:
                        try:
                            r = requests.post(url, json=dados, timeout=2)
                            if r.status_code == 200:
                                backoff_idx = 0
                                enviado = True
                                print(f"Enviado: Temp={dados['temperatura']:.2f}°C Vazao={dados['vazao']:.2f} Cooler={dados['cooler']}%")
                            else:
                                print(f"Erro API: {r.status_code}")
                                delay = BACKOFF_DELAYS[min(backoff_idx, len(BACKOFF_DELAYS) - 1)]
                                backoff_idx = min(backoff_idx + 1, len(BACKOFF_DELAYS) - 1)
                                print(f"Tentando novamente em {delay}s...")
                                time.sleep(delay)
                        except requests.RequestException as e:
                            delay = BACKOFF_DELAYS[min(backoff_idx, len(BACKOFF_DELAYS) - 1)]
                            backoff_idx = min(backoff_idx + 1, len(BACKOFF_DELAYS) - 1)
                            print(f"Erro ao enviar: {e}. Tentando novamente em {delay}s...")
                            time.sleep(delay)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
