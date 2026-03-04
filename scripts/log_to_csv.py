#!/usr/bin/env python3
"""Junta logs seriais e converte linhas Temp: ... em CSV."""

import re
import sys
from pathlib import Path

PATTERN = re.compile(
    r"Temp:\s*([\d.]+)\s*C\s*\|\s*Vazao:\s*([\d.]+)\s*L/min\s*\|\s*Cooler:\s*(\d+)%\s*\|\s*Resistencia:\s*(ON|OFF)",
    re.IGNORECASE,
)


def parse_log(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        m = PATTERN.match(line)
        if m:
            rows.append({
                "temp_C": float(m.group(1)),
                "vazao_L_min": float(m.group(2)),
                "cooler_pct": int(m.group(3)),
                "resistencia": m.group(4),
            })
    return rows


def main():
    logs_dir = Path(__file__).resolve().parent.parent / "logs"
    log1 = logs_dir / "serial_20260304_191404.log"
    log2 = logs_dir / "serial_20260304_193023.log"
    out_csv = logs_dir / "serial_combinado_20260304.csv"

    rows1 = parse_log(log1)
    rows2 = parse_log(log2)
    combined = rows1 + rows2

    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("temp_C,vazao_L_min,cooler_pct,resistencia\n")
        for r in combined:
            f.write(f"{r['temp_C']:.2f},{r['vazao_L_min']:.2f},{r['cooler_pct']},{r['resistencia']}\n")

    print(f"Arquivo 1: {len(rows1)} linhas | Arquivo 2: {len(rows2)} linhas | Total: {len(combined)}")
    print(f"CSV salvo em: {out_csv}")


if __name__ == "__main__":
    main()
