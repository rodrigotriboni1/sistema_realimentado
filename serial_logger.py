"""
Captura dados do ensaio de identificação G_F(s) via Serial (ESP32).

Formato esperado do ESP32:
  Linhas de comentário  →  começam com '#' (ignoradas no CSV)
  Cabeçalho             →  t_ms,vazao_Lmin,fase
  Dados                 →  <inteiro>,<float>,<INICIAL|DEGRAU|CONCLUIDO>

Saída: arquivo CSV pronto para plotagem e identificação de G_F(s).
"""

import serial
import csv
import sys
from datetime import datetime
from pathlib import Path

# ── Configurações ──────────────────────────────────────────────────────────────
PORTA_SERIAL = "COM6"
BAUD_RATE    = 115200
ARQUIVO_CSV  = f"ensaio_GF_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

COLUNAS_ESP  = ["t_ms", "vazao_Lmin", "fase"]   # cabeçalho enviado pelo ESP32
COLUNAS_CSV  = ["t_ms", "vazao_Lmin", "fase"]    # colunas gravadas no arquivo
# ──────────────────────────────────────────────────────────────────────────────


def conectar(porta: str, baud: int) -> serial.Serial:
    print(f"Conectando em {porta} @ {baud} baud...")
    try:
        ser = serial.Serial(porta, baud, timeout=2)
        print("Conectado! Aguardando dados do ESP32...\n")
        return ser
    except serial.SerialException as e:
        print(f"[ERRO] Não foi possível abrir {porta}: {e}")
        print("Verifique a porta e se o ESP32 está conectado.")
        sys.exit(1)


def parsear_linha(linha: str) -> dict | None:
    """
    Interpreta uma linha de dados CSV enviada pelo ESP32.
    Retorna dict com as colunas ou None se a linha for inválida/comentário.
    """
    linha = linha.strip()

    # Ignora comentários e linhas vazias
    if not linha or linha.startswith("#"):
        return None

    # Ignora o cabeçalho enviado pelo ESP32 (re-enviado a cada reset)
    if linha.startswith("t_ms"):
        return None

    partes = linha.split(",")
    if len(partes) != 3:
        return None

    try:
        return {
            "t_ms":      int(partes[0]),
            "vazao_Lmin": float(partes[1]),
            "fase":      partes[2].upper(),
        }
    except ValueError:
        return None


def main():
    ser = conectar(PORTA_SERIAL, BAUD_RATE)

    caminho = Path(ARQUIVO_CSV)
    print(f"Gravando em: {caminho.resolve()}")
    print("-" * 60)
    print(f"{'t_ms':>8}  {'vazao (L/min)':>14}  fase")
    print("-" * 60)

    amostras = 0
    vazao_rp = None

    try:
        with open(ARQUIVO_CSV, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=COLUNAS_CSV)
            writer.writeheader()

            while True:
                linha_raw = ser.readline().decode("utf-8", errors="ignore")

                # Repassa comentários do ESP32 direto para o terminal
                linha_strip = linha_raw.strip()
                if linha_strip.startswith("#"):
                    print(f"  {linha_strip}")

                    # Captura a vazão de regime permanente anunciada pelo firmware
                    if "Vazao_RP" in linha_strip:
                        try:
                            vazao_rp = float(linha_strip.split("=")[1].split()[0])
                        except (IndexError, ValueError):
                            pass
                    continue

                dados = parsear_linha(linha_raw)
                if dados is None:
                    continue

                writer.writerow(dados)
                csvfile.flush()
                amostras += 1

                print(f"  {dados['t_ms']:>8}  {dados['vazao_Lmin']:>14.4f}  {dados['fase']}")

                # Encerra automaticamente após confirmar regime permanente
                if dados["fase"] == "CONCLUIDO" and vazao_rp is not None:
                    # Aguarda mais algumas amostras de confirmação (≈ 2 s)
                    confirmacoes = 0
                    while confirmacoes < 10:
                        linha_raw = ser.readline().decode("utf-8", errors="ignore")
                        dados_extra = parsear_linha(linha_raw)
                        if dados_extra:
                            writer.writerow(dados_extra)
                            csvfile.flush()
                            amostras += 1
                            confirmacoes += 1
                            print(f"  {dados_extra['t_ms']:>8}  {dados_extra['vazao_Lmin']:>14.4f}  {dados_extra['fase']}")
                    break

    except KeyboardInterrupt:
        print("\n\nInterrompido pelo usuário.")
    finally:
        ser.close()
        print("-" * 60)
        print(f"Total de amostras gravadas : {amostras}")
        if vazao_rp is not None:
            print(f"Vazão em regime permanente : {vazao_rp:.4f} L/min  (setpoint máximo)")
        print(f"Arquivo salvo em           : {Path(ARQUIVO_CSV).resolve()}")
        print("Porta serial fechada.")


if __name__ == "__main__":
    main()
