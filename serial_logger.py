"""
Captura dados do ESP32 via Serial e grava em CSV.

Suporta quatro formatos de firmware:

  [1] Ensaio open-loop temperatura (PWM_Temp=100%, Cooler=0%):
        Temp: 35.50 C | DC_Temp: 100% | DC_Cooler: 0%

  [2] Ensaio com PID (variacao de SP):
        Temp: 38.50 C | SP_Temp: 40.0 C | Fase: AQUECENDO | Estab: 2/5 |
        Vazao: 0.00 L/min | SP_Vazao: 0.0 |
        DC_Cooler: 0% | DC_Resist: 75% | Resistencia: ON

  [3] Ensaio open-loop fluxo (PWM_Temp=0%, Cooler=100%):
        Vazao: 3.20 L/min | Pulsos: 24 | DC_Temp: 0% | DC_Cooler: 100%

  [4] Ensaio degrau: Resist. 100% -> estabilizar -> Cooler 100% -> estabilizar:
        Temp: 52.10 C | Fase: COOLER_MAX | Estab: 3/5 |
        Vazao: 2.50 L/min | DC_Temp: 100% | DC_Cooler: 100%
"""

import serial
import csv
import re
from datetime import datetime
from typing import Optional
import time

# ── Configuracoes ──────────────────────────────────────────────────────────────
PORTA_SERIAL = "COM7"
BAUD_RATE    = 115200

# Modo 1: open-loop temp  |  2: PID  |  3: open-loop fluxo  |  4: degrau resist+cooler
MODO = 4
ARQUIVO_CSV = {
    1: "dados_ensaio_openloop_temp.csv",
    2: "dados_ensaio_variacao_sp.csv",
    3: "dados_ensaio_openloop_fluxo.csv",
    4: "dados_ensaio_degrau_cooler.csv",
}.get(MODO, "dados_ensaio.csv")


# ── Parsers ────────────────────────────────────────────────────────────────────
def extrair_openloop(linha: str) -> Optional[dict]:
    """Formato: Temp: 35.50 C | DC_Temp: 100% | DC_Cooler: 0%"""
    padrao = (
        r"Temp:\s*([-\d.]+)\s*C\s*\|\s*"
        r"DC_Temp:\s*(\d+)%\s*\|\s*"
        r"DC_Cooler:\s*(\d+)%"
    )
    m = re.search(padrao, linha)
    if m:
        return {
            "temperatura": float(m.group(1)),
            "dc_temp":     int(m.group(2)),
            "dc_cooler":   int(m.group(3)),
        }
    return None


def extrair_degrau(linha: str) -> Optional[dict]:
    """Formato: Temp: 52.10 C | Fase: COOLER_MAX | Estab: 3/5 | Vazao: 2.50 L/min | DC_Temp: 100% | DC_Cooler: 100%"""
    padrao = (
        r"Temp:\s*([-\d.]+)\s*C\s*\|\s*"
        r"Fase:\s*(\w+)\s*\|\s*"
        r"Estab:\s*(\d+)/(\d+)\s*\|\s*"
        r"Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*"
        r"DC_Temp:\s*(\d+)%\s*\|\s*"
        r"DC_Cooler:\s*(\d+)%"
    )
    m = re.search(padrao, linha)
    if m:
        return {
            "temperatura":    float(m.group(1)),
            "fase":           m.group(2),
            "estab_contagem": int(m.group(3)),
            "estab_alvo":     int(m.group(4)),
            "vazao":          float(m.group(5)),
            "dc_temp":        int(m.group(6)),
            "dc_cooler":      int(m.group(7)),
        }
    return None


def extrair_fluxo(linha: str) -> Optional[dict]:
    """Formato: Vazao: 3.20 L/min | Pulsos: 24 | DC_Temp: 0% | DC_Cooler: 100%"""
    padrao = (
        r"Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*"
        r"Pulsos:\s*(\d+)\s*\|\s*"
        r"DC_Temp:\s*(\d+)%\s*\|\s*"
        r"DC_Cooler:\s*(\d+)%"
    )
    m = re.search(padrao, linha)
    if m:
        return {
            "vazao":     float(m.group(1)),
            "pulsos":    int(m.group(2)),
            "dc_temp":   int(m.group(3)),
            "dc_cooler": int(m.group(4)),
        }
    return None


def extrair_pid(linha: str) -> Optional[dict]:
    """Formato completo com SP, fase, estab, vazao."""
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
    if m:
        return {
            "temperatura":    float(m.group(1)),
            "sp_temperatura": float(m.group(2)),
            "fase":           m.group(3),
            "estab_contagem": int(m.group(4)),
            "estab_alvo":     int(m.group(5)),
            "vazao":          float(m.group(6)),
            "sp_vazao":       float(m.group(7)),
            "dc_cooler":      int(m.group(8)),
            "dc_resistencia": int(m.group(9)),
            "resistencia":    m.group(10),
        }
    return None


# ── Cabecalhos CSV ─────────────────────────────────────────────────────────────
CABECALHO_OPENLOOP = [
    "timestamp",
    "temperatura_C",
    "dc_temp_%",
    "dc_cooler_%",
]

CABECALHO_FLUXO = [
    "timestamp",
    "vazao_L_min",
    "pulsos",
    "dc_temp_%",
    "dc_cooler_%",
]

CABECALHO_DEGRAU = [
    "timestamp",
    "temperatura_C",
    "fase",
    "estab_contagem",
    "estab_alvo",
    "vazao_L_min",
    "dc_temp_%",
    "dc_cooler_%",
]

CABECALHO_PID = [
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


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    modo_str = {
        1: "open-loop temperatura",
        2: "PID variacao de SP",
        3: "open-loop fluxo",
        4: "degrau: resist. 100% -> cooler 100%",
    }.get(MODO, "?")
    print(f"Modo: {modo_str}")
    print(f"Porta: {PORTA_SERIAL} | Baud: {BAUD_RATE}")
    print(f"Arquivo de saida: {ARQUIVO_CSV}\n")

    try:
        ser = serial.Serial(PORTA_SERIAL, BAUD_RATE, timeout=1)
        print("Conectado! Aguardando dados...\n")
    except serial.SerialException as e:
        print(f"Erro ao abrir porta serial: {e}")
        return

    cabecalho = {1: CABECALHO_OPENLOOP, 2: CABECALHO_PID, 3: CABECALHO_FLUXO, 4: CABECALHO_DEGRAU}[MODO]
    extrair   = {1: extrair_openloop,   2: extrair_pid,   3: extrair_fluxo,   4: extrair_degrau  }[MODO]

    arquivo_existe = False
    try:
        with open(ARQUIVO_CSV, "r"):
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

                    # Mensagens de evento do firmware
                    if linha.startswith(">>>"):
                        print(f"\n{'='*55}")
                        print(f"  {linha[3:].strip()}")
                        print(f"{'='*55}\n")
                        continue

                    dados = extrair(linha)
                    if not dados:
                        continue

                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    amostras += 1

                    # ── Gravar CSV ──
                    if MODO == 1:
                        writer.writerow([
                            timestamp,
                            dados["temperatura"],
                            dados["dc_temp"],
                            dados["dc_cooler"],
                        ])
                        csvfile.flush()
                        print(
                            f"[{timestamp}] #{amostras:4d} | "
                            f"Temp: {dados['temperatura']:6.2f} C | "
                            f"DC_Temp: {dados['dc_temp']:3d}% | "
                            f"DC_Cooler: {dados['dc_cooler']:3d}%"
                        )

                    elif MODO == 4:
                        writer.writerow([
                            timestamp,
                            dados["temperatura"],
                            dados["fase"],
                            dados["estab_contagem"],
                            dados["estab_alvo"],
                            dados["vazao"],
                            dados["dc_temp"],
                            dados["dc_cooler"],
                        ])
                        csvfile.flush()

                        if dados["fase"] != fase_anterior:
                            print(f"\n--- Fase: {dados['fase']} ---")
                            fase_anterior = dados["fase"]

                        n    = dados["estab_contagem"]
                        alvo = dados["estab_alvo"]
                        barra = "#" * n + "." * max(0, alvo - n)
                        print(
                            f"[{timestamp}] #{amostras:4d} | "
                            f"Temp: {dados['temperatura']:6.2f} C | "
                            f"Fase: {dados['fase']:<12} | "
                            f"Estab: [{barra}] {n}/{alvo} | "
                            f"Vazao: {dados['vazao']:.2f} L/min | "
                            f"DC_Temp: {dados['dc_temp']:3d}% | "
                            f"DC_Cooler: {dados['dc_cooler']:3d}%"
                        )

                    elif MODO == 3:
                        writer.writerow([
                            timestamp,
                            dados["vazao"],
                            dados["pulsos"],
                            dados["dc_temp"],
                            dados["dc_cooler"],
                        ])
                        csvfile.flush()
                        print(
                            f"[{timestamp}] #{amostras:4d} | "
                            f"Vazao: {dados['vazao']:6.2f} L/min | "
                            f"Pulsos: {dados['pulsos']:3d} | "
                            f"DC_Temp: {dados['dc_temp']:3d}% | "
                            f"DC_Cooler: {dados['dc_cooler']:3d}%"
                        )

                    else:
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

                        # Aviso de troca de fase
                        if dados["fase"] != fase_anterior:
                            print(f"\n--- Fase: {dados['fase']} ---")
                            fase_anterior = dados["fase"]

                        n    = dados["estab_contagem"]
                        alvo = dados["estab_alvo"]
                        barra = "#" * n + "." * max(0, alvo - n)
                        print(
                            f"[{timestamp}] #{amostras:4d} | "
                            f"Temp: {dados['temperatura']:6.2f} C | "
                            f"SP: {dados['sp_temperatura']:.1f} C | "
                            f"Fase: {dados['fase']:<12} | "
                            f"Estab: [{barra}] {n}/{alvo} | "
                            f"Vazao: {dados['vazao']:.2f} L/min | "
                            f"Cooler: {dados['dc_cooler']:3d}%"
                        )

                time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\nEncerrado. {amostras} amostras gravadas em {ARQUIVO_CSV}")
    finally:
        ser.close()
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
