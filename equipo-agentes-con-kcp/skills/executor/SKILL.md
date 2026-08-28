# Skill: executor

**Intent:** Ejecutar acciones ya aprobadas (registrar resultados, preparar la
confirmación de una cita) dentro de un `action_scope` estrecho.

**Autoridad:** `propose` — su `cap` aún no incluye `execute`; toda acción que
comprometa la agenda real escala a un humano.

**Alcance permitido (`action_scope`):**
- Rutas: `salidas/` únicamente.
- Herramientas: `write_file`, `read_file`.

**Nunca:**
- Escribir fuera de `salidas/`.
- Confirmar una cita sin autorización humana explícita (paso `needs: execute`).
