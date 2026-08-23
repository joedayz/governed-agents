# Ejercicio: Un equipo de agentes gobernado

> **Idea central**:
> *La autonomia no es un interruptor: es un techo por paso.*
> Un agente propone; una regla decide si puede; un humano firma lo irreversible;
> y todo queda registrado en una cadena verificable.

## Qué construimos

Un equipo de **4 agentes** que gestiona una solicitud de cita en una
clinica, coordinados por un **orquestador** que no es un LLM: es un
loop de Python que aplica reglas.

| Agente | ¿Usa LLM? | Capacidad ganada (cap) | Hace |
|---|---|---|---|
| retriever | ✅ | explain | Lee y resume protocolos y FAQ |
| assessor  | ❌ | propose | Calcula el hecho clinico con reglas |
| drafter   | ✅ | propose | Redacta la respuesta al paciente |
| executor  | ❌ | propose | Ejecuta acciones (solo en `salidas/`) |

**Leccion 1:** no todo agente necesita un LLM. "Este caso es prioridad
media" puede salir de reglas claras; se computa, no se le pregunta a un modelo.

## Las 3 reglas del juego

Escala de autoridad: `observe(1) < explain(2) < propose(3) < prepare(4) < execute(5)`

1. **«lowest-of»**: la autoridad efectiva de un paso es
   `min(granted del paso, cap del agente)`. Nunca el máximo.
2. **Brecha → escalar**: si el paso `needs` más autoridad que la efectiva,
   la diferencia se calcula (`short by N`) y el paso se detiene hasta que
   un humano firme. No es un `if` mágico: es aritmética sobre la escala.
3. **Fail-closed**: lo no declarado está prohibido. El executor solo puede
   escribir en `salidas/` porque eso dice su `action_scope`.

## Los 4 desenlaces de un paso (badges)

- `✓ autonomous` — la autoridad alcanza: el agente actúa solo.
- `i informed` — se notifica a un humano (FYI, no bloquea).
- `🔒 authorized` — se detiene hasta que un humano autorice (paso 5: dinero).
- `+ learning` — el agente propone mejorar una regla; el humano acepta o no.

**Leccion 2:** el humano no vigila todo; se le pregunta *rara vez y con
precision*, y su firma queda en el ledger igual que la de los agentes.

## Como probarlo

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### Sin Anthropic (modo simulado)

```bash
# Todo simulado, ideal para clase o demo local
python3 orquestador.py --sim

python3 orquestador.py --sim --caso alta
python3 orquestador.py --sim --caso media
python3 orquestador.py --sim --caso baja
python3 orquestador.py --sim --caso borde
```

### Con Anthropic

```bash
# Carga tu API key local
source /Users/josediaz/.api-keys

# Verifica que ANTHROPIC_API_KEY este disponible
python3 -c "import os; print('ok' if os.getenv('ANTHROPIC_API_KEY') else 'missing')"

# Usa el modelo real para retriever y drafter
python3 orquestador.py --caso alta
python3 orquestador.py --caso media
python3 orquestador.py --caso baja
python3 orquestador.py --caso borde
```

Casos disponibles:

- `alta`: dolor de pecho y falta de aire
- `media`: fiebre leve y dolor de garganta
- `baja`: chequeo general
- `borde`: tos leve

En ambos modos:

- `retriever` y `drafter` usan simulacion o modelo real segun el flag `--sim`
- `assessor` y `executor` siguen siendo deterministas y no usan LLM

## Archivos (léelos en este orden)

1. `knowledge.yaml` — el equipo, el playbook, las autoridades. **Todo es dato,
   no código**: cambiar las reglas no requiere tocar Python.
2. `escala.py` — 15 líneas: la escala, «lowest-of» y la brecha.
3. `ledger.py` — recibos con hash encadenado + verificación.
4. `agentes.py` — los 4 especialistas.
5. `orquestador.py` — el loop que une todo.

## Retos para el alumno

1. **Cambia los sintomas** en `orquestador.py` a "dolor de pecho y falta de aire".
  ¿Que pasos cambian? ¿Por que ya no conviene tratar el caso como una cita normal?
2. **Sube el cap del executor** a `execute` en `knowledge.yaml`.
  ¿Que paso deja de escalar? ¿Te parece buena idea? (La capacidad se *gana* con track record;
  y se pierde con la primera desviación.)
3. **Rompe el ledger**: edita a mano una línea de `ledger.jsonl` y vuelve a
  correr. ¿Que imprime `Cadena integra`? ¿Por que?
4. **Ataca el action_scope**: haz que el paso 6 intente escribir en
  `docs/protocolo-triaje.md`. ¿Que devuelve el executor?
5. **Agrega un 5º agente** `auditor` (cap `observe`) que al final lea el
  ledger y produzca un resumen de la corrida. ¿Que `granted` necesita?
6. **Pregunta de ensayo**: ¿por que el paso 5 escala *siempre*, incluso si
  el drafter esta "seguro al 92%"? (Pista: el gate no es
  "que tan seguro esta el modelo", sino "que TIPO de decision es".)

## Que demuestra esta demo

- Como repartir el trabajo entre agentes simples y especializados.
- Como gobernar esos agentes con caps, reglas y escalado humano.
- Como dejar evidencia verificable en un ledger append-only.
- Como preparar el terreno para herramientas mas avanzadas mas adelante.
