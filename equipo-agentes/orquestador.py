#!/usr/bin/env python3
"""EL ORQUESTADOR — recorre el playbook y mantiene a cada agente en su carril.

Por cada paso calcula:
    efectivo = min(granted del paso, cap del agente)      «lowest-of»
    brecha   = needs - efectivo
y decide UNA de cuatro salidas (los badges de la demo):

    ✓ autonomous  la autoridad alcanza -> el agente actúa solo
    i informed    un humano es NOTIFICADO (no bloquea)
    ⛔ authorized  brecha > 0 -> se DETIENE hasta que un humano firme
    + learning    el agente propone una mejora; el humano acepta o rechaza

Uso:
    source /Users/josediaz/.api-keys && .venv/bin/python orquestador.py
    .venv/bin/python orquestador.py --sim        # sin API key
"""
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Falta la dependencia 'PyYAML'. Instalala con:\n"
        "  python3 -m pip install -r requirements.txt\n"
        "o bien:\n"
        "  python3 -m pip install PyYAML anthropic"
    ) from exc

import agentes
from escala import efectivo, brecha
from ledger import Ledger, verificar_cadena

BASE = Path(__file__).parent

# ------------------------------------------------------------------ casos de demo
CASOS = {
    "media": {
        "paciente": "Ana Torres",
        "especialidad": "medicina general",
        "sintomas": "fiebre leve y dolor de garganta desde hace 2 dias",
        "seguro": "activo",
    },
    "alta": {
        "paciente": "Carlos Ruiz",
        "especialidad": "medicina general",
        "sintomas": "dolor de pecho y falta de aire desde esta manana",
        "seguro": "activo",
    },
    "baja": {
        "paciente": "Lucia Perez",
        "especialidad": "medicina general",
        "sintomas": "quiero chequeo general",
        "seguro": "activo",
    },
    "borde": {
        "paciente": "Miguel Soto",
        "especialidad": "medicina general",
        "sintomas": "tos leve desde ayer",
        "seguro": "activo",
    },
}


def obtener_caso(argv: list[str]) -> dict:
    caso_id = "media"
    for i, arg in enumerate(argv):
        if arg == "--caso":
            if i + 1 >= len(argv):
                raise SystemExit("Uso: python3 orquestador.py [--sim] [--caso alta|media|baja|borde]")
            caso_id = argv[i + 1]
            break
        if arg.startswith("--caso="):
            caso_id = arg.split("=", 1)[1]
            break

    if caso_id not in CASOS:
        disponibles = ", ".join(CASOS)
        raise SystemExit(f"Caso desconocido '{caso_id}'. Usa uno de: {disponibles}")
    return CASOS[caso_id]


def preguntar_humano(pregunta: str) -> bool:
    """El humano es un ACTOR más de la corrida: su decisión también se firma."""
    return input(f"\n  🧑 HUMANO, {pregunta} [s/n]: ").strip().lower().startswith("s")


def main():
    agentes.SIM = "--sim" in sys.argv
    caso = obtener_caso(sys.argv[1:])
    manifest = yaml.safe_load((BASE / "knowledge.yaml").read_text())
    equipo = manifest["agentes"]
    ledger = Ledger()
    memoria = {}          # resultados que fluyen de un paso al siguiente

    print(f"\n{'='*62}\n  PLAYBOOK: gestionar-cita-clinica   corr={ledger.corr}"
          f"\n  Caso: {caso['paciente']} · {caso['especialidad']} · {caso['sintomas']}\n{'='*62}")

    for paso in manifest["playbook"]["pasos"]:
        agente, granted, needs = paso["agente"], paso["granted"], paso["needs"]
        cap = equipo[agente]["cap"]
        nivel = efectivo(granted, cap)              # «lowest-of»
        falta = brecha(needs, nivel)
        detalle = ""

        print(f"\n[{paso['id']}] {paso['titulo']}")
        print(f"    agente={agente}  granted={granted}  cap={cap}  "
              f"-> efectivo={nivel}  needs={needs}", end="")

        # ---------- ¿la autoridad alcanza? ----------
        if falta > 0:
            print(f"  · short by {falta} -> ESCALAR")
            if not preguntar_humano(f"¿autorizas '{paso['titulo']}'?"):
                ledger.recibo(paso["titulo"], "humano", nivel, "rechazado")
                print("    ⛔ rechazado por el humano — la corrida se detiene aquí.")
                break
            ledger.recibo(paso["titulo"], "humano (authorized)", nivel, "autorizado")
            print("    🔒 authorized — un humano firmó la decisión.")
            memoria["autorizado"] = True
            continue
        print()

        # ---------- el agente trabaja ----------
        if agente == "retriever":
            memoria["resumen"] = agentes.retriever(caso)
            detalle = memoria["resumen"]
        elif agente == "assessor" and paso["id"] == 2:
            memoria["hecho"] = agentes.assessor(caso)
            detalle = str(memoria["hecho"])
            print(f"    HECHO CALCULADO (sin LLM): prioridad={memoria['hecho']['prioridad']}, "
                  f"accion='{memoria['hecho']['accion_sugerida']}'")
        elif agente == "assessor" and paso["id"] == 3:
            if not memoria["hecho"]["caso_limite"]:
                ledger.recibo(paso["titulo"], agente, nivel, "omitido", "no requiere coordinacion")
                print("    (no es un caso que requiera coordinacion)")
                continue
            detalle = f"caso prioridad media: {memoria['hecho']['accion_sugerida']}"
            print(f"    i informed — FYI al coordinador: {detalle} (no bloquea)")
            ledger.recibo(paso["titulo"], f"{agente} -> humano (informed)", nivel, "informado", detalle)
            continue
        elif agente == "drafter":
            memoria["borrador"] = agentes.drafter(caso, memoria["resumen"], memoria["hecho"])
            detalle = memoria["borrador"]
        elif agente == "executor" and paso["id"] == 6:
            detalle = agentes.executor(caso, memoria["borrador"], "salidas/respuesta-cliente.md")
            print(f"    -> {detalle}")
        elif paso.get("tipo_humano") == "learning":
            propuesta = ("Aclarar en el protocolo cuando fiebre leve y dolor de garganta "
                         "deben pasar de prioridad baja a prioridad media.")
            print(f"    + learning — el assessor propone: {propuesta}")
            acepta = preguntar_humano("¿aceptas este aprendizaje para el protocolo?")
            outcome = "learn aceptado" if acepta else "learn rechazado"
            ledger.recibo(paso["titulo"], "humano (learning)", nivel, outcome, propuesta)
            continue
        else:
            raise RuntimeError(f"Paso no soportado por el orquestador: {paso}")

        ledger.recibo(paso["titulo"], agente, nivel, "autonomous", detalle)
        print(f"    ✓ autonomous")

    # ---------------------------------------------------------- cierre
    print(f"\n{'='*62}\n  Cadena íntegra: {verificar_cadena()}   (ledger.jsonl)\n{'='*62}")
    if "borrador" in memoria:
        print("\n--- Borrador para el cliente (salidas/respuesta-cliente.md) ---")
        print(memoria["borrador"])


if __name__ == "__main__":
    main()
