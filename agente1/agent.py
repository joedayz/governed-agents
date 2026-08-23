#!/usr/bin/env python3
"""
agente1 — un agente mínimo con gobernanza estilo KCP.

Las tres piezas (léelas en este orden):
  1. GOBERNANZA  — check_conformance(): función pura, fail-closed, sin LLM.
  2. HERRAMIENTAS — lo único que el agente puede *hacer* en el mundo real.
  3. EL LOOP     — el ciclo LLM -> tool -> resultado -> LLM.

Uso:
  source ~/.api-keys
  .venv/bin/python agent.py "¿Cuál es la política de reembolsos?"
  .venv/bin/python agent.py --sim          # demo sin API (solo gobernanza)
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import yaml

BASE = Path(__file__).parent
LEDGER = BASE / "audit.jsonl"

# ======================================================================
# 1. GOBERNANZA — la parte que Thor diría que nunca debe ser del modelo
# ======================================================================

def load_manifest() -> dict:
    return yaml.safe_load((BASE / "knowledge.yaml").read_text())


def active_skill(manifest: dict) -> dict:
    """El skill bajo el cual actúa el agente (aquí: el único declarado)."""
    for unit in manifest["units"]:
        if unit.get("kind") == "skill":
            return unit
    raise SystemExit("No hay skill declarado: sin autoridad, nada se permite.")


def check_conformance(tool: str, target: str | None, scope: dict) -> dict:
    """Función PURA y fail-closed. Sin I/O, sin modelo, sin azar.
    Cada dimensión declarada es un allowlist. Devuelve veredicto con razón."""
    allowed_tools = scope.get("tools", [])
    allowed_paths = scope.get("paths", [])

    if tool not in allowed_tools:
        return {"passed": False,
                "reason": f'tool "{tool}" está fuera de las tools autorizadas {allowed_tools}'}

    if target is not None and allowed_paths:
        # normalizamos para bloquear escapes tipo ../secrets
        norm = os.path.normpath(target)
        if os.path.isabs(norm) or norm.startswith(".."):
            return {"passed": False,
                    "reason": f'target "{target}" escapa del proyecto (ruta absoluta o ../)'}
        if not any(norm == p.rstrip("/") or norm.startswith(p) for p in allowed_paths):
            return {"passed": False,
                    "reason": f'target "{target}" está fuera de los paths autorizados {allowed_paths}'}

    return {"passed": True,
            "reason": f'acción "{tool}" sobre {target or "(sin target)"} está dentro del action_scope declarado'}


def audit(event: str, **data):
    """Ledger append-only con hash encadenado: cada evento apunta al anterior."""
    prev = "genesis"
    if LEDGER.exists():
        lines = LEDGER.read_text().strip().splitlines()
        if lines:
            prev = json.loads(lines[-1])["hash"]
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, **data, "prev": prev}
    entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()[:16]
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ======================================================================
# 2. HERRAMIENTAS — el "cuerpo" del agente
# ======================================================================

def tool_read_file(path: str) -> str:
    return (BASE / path).read_text()

def tool_list_files(path: str) -> str:
    return "\n".join(sorted(p.name for p in (BASE / path).iterdir()))

def tool_write_file(path: str, content: str) -> str:
    target = BASE / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"escrito: {path} ({len(content)} chars)"

TOOL_IMPLS = {"read_file": tool_read_file, "list_files": tool_list_files,
              "write_file": tool_write_file}

TOOL_DEFS = [  # lo que el LLM ve: nombre + parámetros, nada más
    {"name": "read_file", "description": "Lee un archivo del proyecto",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "list_files", "description": "Lista archivos de un directorio",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "write_file", "description": "Escribe un archivo",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"},
                                                        "content": {"type": "string"}},
                      "required": ["path", "content"]}},
]


def execute_governed(tool: str, args: dict, scope: dict) -> str:
    """El portero: TODA llamada pasa por aquí. Aprueba o bloquea, y ambas
    cosas quedan en el ledger con su razón escrita."""
    target = args.get("path")
    verdict = check_conformance(tool, target, scope)
    if not verdict["passed"]:
        audit("tool-blocked", tool=tool, target=target, reason=verdict["reason"])
        # el bloqueo se DEVUELVE al modelo como texto: puede autocorregirse
        return f"BLOQUEADO POR GOBERNANZA: {verdict['reason']}"
    audit("tool-approved", tool=tool, target=target, reason=verdict["reason"])
    try:
        return TOOL_IMPLS[tool](**args)
    except Exception as e:
        return f"error de ejecución: {e}"


# ======================================================================
# 3. EL LOOP — todo agente del mundo es una variante de estas 30 líneas
# ======================================================================

def run_agent(task: str):
    import anthropic
    client = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY del entorno

    manifest = load_manifest()
    skill = active_skill(manifest)
    scope = skill["action_scope"]

    # El "mapa" KCP entra al system prompt: el agente sabe qué existe,
    # qué responde cada unidad, y cuáles están deprecadas.
    unit_map = "\n".join(
        f'- {u["id"]} ({u["path"]}): {u["intent"]}' + (" [DEPRECATED — no usar]" if u.get("deprecated") else "")
        for u in manifest["units"] if u.get("kind") != "skill")

    system = f"""Eres un agente de soporte de JoeDayz Academy operando bajo el skill
"{skill['id']}". Fundamenta CADA respuesta solo en los documentos del proyecto
(nunca en conocimiento externo). Mapa de conocimiento disponible:
{unit_map}

Al terminar, guarda tu respuesta final en notes/respuesta.md con write_file."""

    audit("run-initiated", task=task, skill=skill["id"], scope=scope)
    messages = [{"role": "user", "content": task}]

    for turn in range(10):                                   # techo, como max_turns
        response = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=1500,
            system=system, tools=TOOL_DEFS, messages=messages)

        messages.append({"role": "assistant", "content": response.content})

        tool_calls = [b for b in response.content if b.type == "tool_use"]
        if not tool_calls:                                   # texto final => fin
            final = "".join(b.text for b in response.content if b.type == "text")
            audit("run-completed", turns=turn + 1)
            print("\n=== RESPUESTA DEL AGENTE ===\n" + final)
            return

        results = []
        for call in tool_calls:
            print(f"  [turno {turn+1}] el modelo pide: {call.name}({json.dumps(call.input, ensure_ascii=False)})")
            output = execute_governed(call.name, call.input, scope)
            print(f"      -> {output[:100]}{'...' if len(output) > 100 else ''}")
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": output})
        messages.append({"role": "user", "content": results})

    audit("run-aborted", reason="max_turns alcanzado")
    print("Detenido: techo de turnos alcanzado.")


# ======================================================================
# Modo --sim: prueba la gobernanza sin API — mismas reglas, cero LLM
# ======================================================================

def run_sim():
    scope = active_skill(load_manifest())["action_scope"]
    audit("run-initiated", task="simulación de gobernanza", skill="soporte-skill", scope=scope)
    print("Simulación: 4 acciones contra el action_scope declarado\n")
    attempts = [
        ("read_file", {"path": "docs/politica-reembolsos.md"}),   # dentro
        ("read_file", {"path": "secrets/api-keys.txt"}),          # fuera: path
        ("read_file", {"path": "docs/../secrets/api-keys.txt"}),  # escape ../
        ("write_file", {"path": "notes/test.md", "content": "ok"}),  # dentro
    ]
    for tool, args in attempts:
        out = execute_governed(tool, args, scope)
        status = "BLOQUEADO" if out.startswith("BLOQUEADO") else "PERMITIDO"
        print(f"  [{status}] {tool}({args.get('path')})")
        if status == "BLOQUEADO":
            print(f"      razón: {out.split(': ', 1)[1]}")
    audit("run-completed", turns=0)
    print(f"\nTodo quedó registrado en {LEDGER.name} (hash encadenado).")


if __name__ == "__main__":
    if "--sim" in sys.argv:
        run_sim()
    elif len(sys.argv) > 1:
        run_agent(" ".join(sys.argv[1:]))
    else:
        print(__doc__)
