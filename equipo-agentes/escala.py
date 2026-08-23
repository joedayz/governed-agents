"""Escala de autoridad y la regla «lowest-of» — el corazón del ejercicio.

    observe(1) < explain(2) < propose(3) < prepare(4) < execute(5)

- cap      = lo que el agente se ha GANADO (vive en knowledge.yaml)
- granted  = lo que el paso le OTORGA
- efectivo = min(cap, granted)          <- nunca el máximo, siempre el menor
- si needs > efectivo -> brecha ("short by N") -> escalar a un humano
"""

NIVELES = {"observe": 1, "explain": 2, "propose": 3, "prepare": 4, "execute": 5}


def efectivo(granted: str, cap: str) -> str:
    """La regla «lowest-of»: la autoridad efectiva es la MENOR de las dos."""
    return granted if NIVELES[granted] <= NIVELES[cap] else cap


def brecha(needs: str, nivel_efectivo: str) -> int:
    """¿Cuántos peldaños faltan? 0 o negativo = alcanza. Positivo = escalar."""
    return NIVELES[needs] - NIVELES[nivel_efectivo]
