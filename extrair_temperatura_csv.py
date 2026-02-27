"""
Extrai dados de temperatura de um texto e gera um arquivo CSV.
Uso:
  python extrair_temperatura_csv.py arquivo.txt
  python extrair_temperatura_csv.py arquivo.txt -o saida.csv
  echo "Temp: 40.48 C | ..." | python extrair_temperatura_csv.py -o saida.csv
"""

import re
import csv
import sys
from typing import List


def extrair_linhas(texto: str) -> List[dict]:
    """
    Extrai temperatura, vazão, cooler e resistência de cada linha.
    Formato: Temp: 40.48 C | Vazao: 0.00 L/min | Cooler: 0% | Resistencia: ON
    """
    padrao = r"Temp:\s*([-\d.]+)\s*C\s*\|\s*Vazao:\s*([-\d.]+)\s*L/min\s*\|\s*Cooler:\s*(\d+)%\s*\|\s*Resistencia:\s*(ON|OFF)"
    dados = []
    for linha in texto.strip().split("\n"):
        match = re.search(padrao, linha.strip())
        if match:
            dados.append({
                "temperatura": float(match.group(1)),
                "vazao": float(match.group(2)),
                "cooler": int(match.group(3)),
                "resistencia": match.group(4),
            })
    return dados


def main():
    # Argumentos
    arquivo_entrada = None
    arquivo_saida = "dados_temperatura.csv"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "-o" and i + 1 < len(args):
            arquivo_saida = args[i + 1]
            i += 2
        else:
            arquivo_entrada = args[i]
            i += 1

    # Ler texto
    if arquivo_entrada:
        with open(arquivo_entrada, "r", encoding="utf-8") as f:
            texto = f.read()
    else:
        texto = sys.stdin.read()

    dados = extrair_linhas(texto)
    if not dados:
        print("Nenhum dado encontrado no texto.")
        sys.exit(1)

    # Gravar CSV
    with open(arquivo_saida, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["indice", "temperatura_C", "vazao_L_min", "cooler_%", "resistencia"])
        for i, d in enumerate(dados, start=1):
            writer.writerow([i, d["temperatura"], d["vazao"], d["cooler"], d["resistencia"]])

    print(f"{len(dados)} linhas extraídas e salvas em {arquivo_saida}")


if __name__ == "__main__":
    main()
