#!/usr/bin/env python3
"""
Captura dados da porta serial (COM) e grava em arquivo.
Útil para registrar a saída do ESP32 durante os ensaios de identificação.

Uso:
  python serial_logger.py                     # lista portas e pede escolha
  python serial_logger.py COM3               # monitoramento normal
  python serial_logger.py COM3 --ensaio      # envia "ENSAIO" ao conectar (ensaio G_T)
  python serial_logger.py COM3 --gf          # envia "ENSAIO_GF" ao conectar (ensaio G_F)
  python serial_logger.py COM3 -o dados.csv  # força nome do CSV de saída

O cabeçalho do CSV é detectado automaticamente a partir do firmware
(linhas "time_ms,temp_C" ou "time_ms,vazao_L_min").
"""

import argparse
import sys
import time
import re
import os
from datetime import datetime

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Instale pyserial: pip install pyserial")
    sys.exit(1)

BAUD = 115200
DEFAULT_LOG_DIR = "logs"

# Linhas de dados numéricos: "time_ms,v1,v2,..."  ex: "2000,25.30,1.50,100"
DATA_LINE_RE = re.compile(r"^\d+(?:,\d+\.?\d*)+\s*$")
# Cabeçalho enviado pelo firmware: "time_ms,col1,col2,..."
HEADER_LINE_RE = re.compile(r"^time_ms(?:,\w+)+$")


def list_ports():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("Nenhuma porta COM encontrada.")
        return None
    print("Portas disponíveis:")
    for i, p in enumerate(ports):
        print(f"  {i}: {p.device} - {p.description}")
    return ports


def main():
    parser = argparse.ArgumentParser(description="Captura dados da porta serial.")
    parser.add_argument("port", nargs="?", help="Porta serial (ex: COM3, /dev/ttyUSB0)")
    parser.add_argument("-b", "--baud", type=int, default=BAUD, help=f"Baud rate (padrão: {BAUD})")
    parser.add_argument("-o", "--csv", metavar="ARQUIVO", help="Caminho do CSV de saída")
    parser.add_argument("--ensaio", action="store_true", help='Envia "ENSAIO" ao conectar (identificação G_T)')
    parser.add_argument("--gf", action="store_true", help='Envia "ENSAIO_GF" ao conectar (identificação G_F)')
    parser.add_argument("--no-log", action="store_true", help="Não gravar log completo")
    parser.add_argument("-d", "--dir", default=DEFAULT_LOG_DIR, help=f"Pasta para logs (padrão: {DEFAULT_LOG_DIR})")
    args = parser.parse_args()

    port = args.port
    if not port:
        ports = list_ports()
        if not ports:
            sys.exit(1)
        try:
            idx = int(input("Número da porta: ").strip())
            port = ports[idx].device
        except (ValueError, IndexError):
            print("Porta inválida.")
            sys.exit(1)

    try:
        ser = serial.Serial(port, args.baud, timeout=0.1)
    except serial.SerialException as e:
        print(f"Erro ao abrir {port}: {e}")
        sys.exit(1)

    # Arquivo de log completo
    log_file = None
    log_path = None
    if not args.no_log:
        os.makedirs(args.dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(args.dir, f"serial_{ts}.log")
        log_file = open(log_path, "w", encoding="utf-8")
        print(f"Log completo: {log_path}")

    # CSV de dados (cabeçalho será detectado dinamicamente)
    csv_file = None
    csv_path = args.csv
    if not csv_path and not args.no_log:
        os.makedirs(args.dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "gf" if args.gf else "ensaio"
        csv_path = os.path.join(args.dir, f"{suffix}_{ts}.csv")
    if csv_path:
        csv_file = open(csv_path, "w", encoding="utf-8")
        print(f"CSV: {csv_path}")

    csv_header_written = False  # True depois que o cabeçalho for gravado no CSV

    # Enviar comando de ensaio
    if args.gf:
        time.sleep(0.5)  # aguarda ESP32 reinicializar
        ser.write(b"ENSAIO_GF\n")
        print('Comando "ENSAIO_GF" enviado.')
    elif args.ensaio:
        time.sleep(0.5)
        ser.write(b"ENSAIO\n")
        print('Comando "ENSAIO" enviado.')

    print(f"Lendo de {port} @ {args.baud}. Ctrl+C para parar.\n")

    try:
        while True:
            line = ser.readline()
            if not line:
                time.sleep(0.01)
                continue
            try:
                text = line.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = line.decode("latin-1", errors="replace").rstrip()
            if not text:
                continue

            print(text)

            if log_file:
                log_file.write(text + "\n")
                log_file.flush()

            if csv_file:
                # Detectar cabeçalho enviado pelo firmware ("time_ms,temp_C" ou "time_ms,vazao_L_min")
                if not csv_header_written and HEADER_LINE_RE.match(text.strip()):
                    csv_file.write(text.strip() + "\n")
                    csv_file.flush()
                    csv_header_written = True
                    continue

                # Gravar linhas de dados numéricos
                if DATA_LINE_RE.match(text.strip()):
                    if not csv_header_written:
                        # Fallback: cabeçalho genérico caso o firmware não o envie
                        csv_file.write("time_ms,valor\n")
                        csv_file.flush()
                        csv_header_written = True
                    csv_file.write(text.strip() + "\n")
                    csv_file.flush()

    except KeyboardInterrupt:
        print("\nInterrompido.")
    finally:
        if log_file:
            log_file.close()
        if csv_file:
            csv_file.close()
        ser.close()


if __name__ == "__main__":
    main()
