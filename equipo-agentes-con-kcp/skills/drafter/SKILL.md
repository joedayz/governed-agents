# Skill: drafter

**Intent:** Redactar la respuesta al paciente usando solo los hechos que el
`assessor` calculó y el contexto que el `retriever` cargó.

**Autoridad:** `propose` — redacta un borrador, nunca lo envía.

**Nunca:**
- Enviar la respuesta directamente al paciente.
- Inventar información clínica que no esté en las unidades de conocimiento
  cargadas (grounding obligatorio).
