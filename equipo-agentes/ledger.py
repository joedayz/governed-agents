"""Ledger append-only con hash encadenado: la "cadena de decisiones firmada".

Cada recibo apunta al hash del anterior. Si alguien edita un recibo viejo,
la cadena se rompe y la manipulacion es detectable. Aqui usamos hashes
SHA-256 para mantener la idea simple y verificable.
"""
import hashlib
import json
import time
import uuid
from pathlib import Path

ARCHIVO = Path(__file__).parent / "ledger.jsonl"


class Ledger:
    def __init__(self):
        self.corr = "run-" + uuid.uuid4().hex[:6]   # un id ata TODA la corrida
        self.seq = 0

    def recibo(self, paso: str, actor: str, efectivo: str, outcome: str, detalle: str = ""):
        self.seq += 1
        prev = "genesis"
        if ARCHIVO.exists():
            lineas = ARCHIVO.read_text().strip().splitlines()
            if lineas:
                prev = json.loads(lineas[-1])["hash"]
        r = {"corr": self.corr, "seq": self.seq,
             "ts": time.strftime("%H:%M:%S"),
             "paso": paso, "actor": actor,
             "efectivo": efectivo, "outcome": outcome,
             "detalle": detalle[:120], "prev": prev}
        r["hash"] = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]
        with ARCHIVO.open("a") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return r


def verificar_cadena() -> bool:
    """Cualquiera puede re-verificar la cadena: eso la hace evidencia."""
    prev = "genesis"
    for linea in ARCHIVO.read_text().strip().splitlines():
        r = json.loads(linea)
        h = r.pop("hash")
        if r["prev"] != prev:                      # ¿el eslabón apunta al anterior?
            return False
        recalculado = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]
        if recalculado != h:                       # ¿el contenido fue alterado?
            return False
        prev = h
    return True
