# FAQ — Agenda de citas

**¿Cuánto tarda en confirmarse una cita?**
Prioridad alta: mismo día. Prioridad media: 24-48h. Prioridad baja: 5-10 días hábiles.

**¿Quién puede cancelar o mover una cita ya confirmada?**
Solo un coordinador humano. Ningún agente tiene autoridad `execute` sobre
citas ya confirmadas — solo puede `propose` un cambio.

**¿Dónde quedan registradas las decisiones del equipo de agentes?**
En el ledger append-only (`ledger.jsonl`) y en las salidas de
`kcp-agent plan --trace`, que documentan por qué cada unidad de conocimiento
fue cargada o descartada.
