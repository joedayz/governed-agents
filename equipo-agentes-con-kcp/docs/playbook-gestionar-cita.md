# Playbook: gestionar-cita-clinica

Procedimiento compuesto y gobernado (`kind: playbook`) que coordina a los
cuatro agentes especializados para procesar una solicitud de cita.

## Pasos

1. **retriever** (`explain`) — recupera el protocolo de triaje y la FAQ
   relevantes al caso.
2. **assessor** (`propose`) — calcula la prioridad clínica y la ventana de
   atención con reglas deterministas.
3. **assessor → humano** (`inform`) — si la prioridad es media, notifica al
   coordinador (FYI, no bloquea).
4. **drafter** (`propose`) — redacta la respuesta al paciente, con
   grounding obligatorio contra las unidades cargadas.
5. **executor → humano** (`authorized`) — confirmar la cita compromete la
   agenda real (`needs: execute`); el `cap` del executor es `propose`, así
   que este paso **siempre** escala a un humano.
6. **executor** (`autonomous`) — registra el resultado en `salidas/`; su
   `action_scope` ya lo permite sin intervención humana.
7. **assessor → humano** (`learning`) — puede proponer una mejora al
   protocolo; el humano acepta o rechaza el aprendizaje.

## Techo del playbook (`action_scope`)

Ningún paso puede exceder `propose`, sin importar lo que un paso individual
`otorgue` (`granted`). Esto es lo que impide que un paso "se escape" del
procedimiento que lo contiene — la misma regla que documenta
`equipo-agentes/knowledge.yaml`, aquí expresada en el vocabulario nativo de
KCP (`kind: playbook`, RFC-0027).
