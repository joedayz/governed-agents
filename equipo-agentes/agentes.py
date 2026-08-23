"""Los 4 agentes especialistas.

No todo agente necesita un LLM.
  - retriever y drafter usan LLM (tareas de lenguaje)
  - assessor y executor son codigo (hechos calculados y acciones acotadas)
Un hecho calculado no se le pide a un modelo: se computa con reglas.
"""
from pathlib import Path

BASE = Path(__file__).parent
SIM = False   # el orquestador lo activa con --sim (sin API, respuestas fijas)


def _llm(prompt: str) -> str:
    """Única puerta al modelo. En modo --sim devuelve texto fijo."""
    if SIM:
        if prompt.startswith("Resume en 3 líneas"):
            return (
                "El protocolo clasifica los casos en prioridad alta, media o baja.\n"
                "Los sintomas con signos de alarma van a urgencias; los casos medios se atienden en 24 horas.\n"
                "La confirmacion final de la cita se envia por correo o SMS."
            )
        if prompt.startswith("Redacta una respuesta breve"):
            return (
                "Hola,\n\n"
                "Gracias por contactarnos. Hemos revisado tu solicitud y la clasificamos como "
                "un caso de prioridad media.\n\n"
                "Por los sintomas reportados, podemos ofrecerte una cita de medicina general "
                "dentro de las proximas 24 horas. En breve te confirmaremos el horario disponible "
                "por correo o SMS.\n\n"
                "Si presentas dificultad para respirar, dolor en el pecho o empeoramiento repentino, "
                "acude a urgencias de inmediato.\n\n"
                "Saludos cordiales."
            )
        return "(simulado)"
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(model="claude-sonnet-4-5", max_tokens=500,
                                  messages=[{"role": "user", "content": prompt}])
    return resp.content[0].text


# ---------------------------------------------------------------- retriever
def retriever(caso: dict) -> str:
    """LLM con autoridad 'explain': solo puede resumir, jamás decidir."""
    protocolo = (BASE / "docs/protocolo-triaje.md").read_text()
    faq = (BASE / "docs/faq-citas.md").read_text()
    return _llm(f"Resume en 3 líneas, en español, lo relevante de estos documentos "
                f"para una solicitud de cita clinica:\n{protocolo}\n{faq}")


# ---------------------------------------------------------------- assessor
def assessor(caso: dict) -> dict:
    """SIN LLM. Calcula prioridad y accion sugerida con reglas deterministicas."""
    sintomas = caso["sintomas"].lower()
    if any(token in sintomas for token in ["dolor de pecho", "falta de aire", "desmayo"]):
        prioridad = "alta"
        accion = "derivar a urgencias de inmediato"
    elif any(token in sintomas for token in ["fiebre", "dolor de garganta", "tos", "vomitos"]):
        prioridad = "media"
        accion = "ofrecer cita dentro de 24 horas"
    else:
        prioridad = "baja"
        accion = "ofrecer cita regular en 2 a 5 dias"
    return {
        "prioridad": prioridad,
        "accion_sugerida": accion,
        "caso_limite": prioridad == "media",
        "requiere_urgencias": prioridad == "alta",
        "regla": "protocolo vigente: alta->urgencias, media->24h, baja->2-5 dias",
    }


# ---------------------------------------------------------------- drafter
def drafter(caso: dict, resumen: str, hecho: dict) -> str:
    """LLM con autoridad 'propose': redacta, pero no envía nada."""
    if SIM:
        if hecho["prioridad"] == "alta":
            return (
                "Hola,\n\n"
                "Gracias por contactarnos. Por los sintomas reportados, este caso requiere "
                "atencion inmediata.\n\n"
                "Te recomendamos acudir a urgencias de inmediato en lugar de esperar una cita "
                "regular. Si lo deseas, luego podemos ayudarte a coordinar el seguimiento.\n\n"
                "Saludos cordiales."
            )
        if hecho["prioridad"] == "media":
            return (
                "Hola,\n\n"
                "Gracias por contactarnos. Hemos revisado tu solicitud y la clasificamos como "
                "un caso de prioridad media.\n\n"
                "Por los sintomas reportados, podemos ofrecerte una cita de medicina general "
                "dentro de las proximas 24 horas. En breve te confirmaremos el horario disponible "
                "por correo o SMS.\n\n"
                "Si presentas dificultad para respirar, dolor en el pecho o empeoramiento repentino, "
                "acude a urgencias de inmediato.\n\n"
                "Saludos cordiales."
            )
        return (
            "Hola,\n\n"
            "Gracias por contactarnos. Hemos revisado tu solicitud y la clasificamos como "
            "un caso de prioridad baja.\n\n"
            "Podemos ofrecerte una cita regular de medicina general entre los proximos 2 y 5 dias. "
            "En breve te enviaremos opciones de horario por correo o SMS.\n\n"
            "Si tus sintomas empeoran, vuelve a escribirnos o acude a urgencias.\n\n"
            "Saludos cordiales."
        )
    return _llm(
        f"Redacta una respuesta breve y amable en español para un paciente que solicita una cita "
        f"de {caso['especialidad']}. "
        f"Hecho calculado: prioridad {hecho['prioridad']}; accion sugerida: {hecho['accion_sugerida']}; "
        f"regla aplicada: {hecho['regla']}. "
        f"Sintomas reportados: {caso['sintomas']}. "
        f"Contexto: {resumen}"
    )


# ---------------------------------------------------------------- executor
def executor(caso: dict, borrador: str, ruta: str) -> str:
    """SIN LLM. Escribe SOLO dentro de su action_scope (salidas/) — fail-closed."""
    if not ruta.startswith("salidas/") or ".." in ruta:
        return f"BLOQUEADO: '{ruta}' está fuera del action_scope [salidas/]"
    destino = BASE / ruta
    destino.write_text(borrador)
    return f"escrito {ruta}"
