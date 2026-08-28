#!/usr/bin/env -S npx tsx
// orquestador.ts
//
// Orquestador REAL: no reimplementa las reglas de KCP, las llama.
//   - kcp-agent.loadManifest / plan   -> decide qué unidades cargar para el caso
//   - kcp-harness.checkConformance    -> decide si una acción de un skill es legal
//
// Es el equivalente de equipo-agentes/orquestador.py, pero en vez de un
// escala.py + ledger.py caseros, delega toda la gobernanza a las
// librerías oficiales del ecosistema KCP — y en vez de Python, en
// TypeScript, para que los tipos de los propios paquetes (`ActionScope`,
// `ObservedAction`, `ConformanceVerdict`, `Manifest`, `AgentPlan`) atrapen
// en tiempo de compilación cualquier uso incorrecto de la API de KCP.
//
// Uso:
//   npx tsx orquestador.ts "fiebre leve y dolor de garganta"
//   npx tsx orquestador.ts "fiebre leve y dolor de garganta" --romper-alcance

import { loadManifest, plan, type Manifest, type Unit } from "kcp-agent";
import { checkConformance, type ObservedAction, type ConformanceVerdict } from "kcp-harness";
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";

const CASO = process.argv[2] ?? "fiebre leve y dolor de garganta";
const ROMPER_ALCANCE = process.argv.includes("--romper-alcance");

interface PasoAgente {
  agente: string;
  skillId: string;
  accion: ObservedAction;
}

interface PasoResuelto extends PasoAgente {
  cargado: boolean;
  verdicto: ConformanceVerdict;
}

function unit(manifest: Manifest, id: string): Unit {
  const u = manifest.units.find((x) => x.id === id);
  if (!u) throw new Error(`unidad no encontrada en el manifiesto: ${id}`);
  return u;
}

function paso(titulo: string): void {
  console.log(`\n— ${titulo} `.padEnd(70, "—"));
}

async function main(): Promise<void> {
  console.log(`Caso: "${CASO}"`);
  if (ROMPER_ALCANCE) console.log("(modo demo: el executor intentará salirse de su action_scope)");

  // 1) kcp-agent: cargar y planificar --------------------------------------
  paso("1. kcp-agent.plan — ¿qué unidades hacen falta para este caso?");
  const manifest: Manifest = await loadManifest(".");
  const resultado = plan(manifest, `Procesar la solicitud de cita de un paciente con ${CASO}`, {
    maxUnits: 6,
  });

  for (const cargado of resultado.selected) {
    console.log(`  ✓ cargado   ${cargado.id.padEnd(24)} (${cargado.reasons.join("; ")})`);
  }
  for (const saltado of resultado.skipped ?? []) {
    console.log(`  · saltado   ${saltado.id.padEnd(24)} (${saltado.reason})`);
  }

  const idsCargados = new Set(resultado.selected.map((u) => u.id));

  // 2) Simular el equipo de agentes, cada uno como una "acción observada" --
  paso("2. Equipo de agentes — cada acción se adjudica con kcp-harness.checkConformance");

  const pasos: PasoAgente[] = [
    {
      agente: "retriever",
      skillId: "retriever-skill",
      accion: { tool: "read_file", paths: ["docs/protocolo-triaje.md"] },
    },
    {
      agente: "assessor",
      skillId: "assessor-skill",
      accion: { tool: "read_file", paths: ["docs/protocolo-triaje.md"] },
    },
    {
      agente: "drafter",
      skillId: "drafter-skill",
      accion: { tool: "read_file", paths: ["docs/faq-agenda.md"] },
    },
    {
      agente: "executor",
      skillId: "executor-skill",
      // Con --romper-alcance, el executor intenta escribir FUERA de salidas/.
      accion: ROMPER_ALCANCE
        ? { tool: "write_file", paths: ["docs/protocolo-triaje.md"] }
        : { tool: "write_file", paths: ["salidas/resultado.json"] },
    },
  ];

  const resultados: PasoResuelto[] = [];

  for (const p of pasos) {
    const u = unit(manifest, p.skillId);
    const verdicto = checkConformance(p.accion, u.action_scope ?? {});
    const marca = verdicto.passed ? "✓ PERMITIDO" : "✗ DENEGADO ";
    console.log(
      `  ${marca}  ${p.agente.padEnd(10)} tool=${p.accion.tool.padEnd(11)} ` +
        `target=${(p.accion.paths ?? []).join(",")}`
    );
    console.log(`              razón: ${verdicto.reason}`);
    resultados.push({ ...p, cargado: idsCargados.has(p.skillId), verdicto });
  }

  // 3) Registrar el resultado — solo si el executor quedó autorizado -------
  paso("3. Registro del resultado en salidas/");
  const pasoExecutor = resultados.find((r) => r.agente === "executor");
  if (!pasoExecutor) throw new Error("paso del executor no encontrado");

  if (pasoExecutor.verdicto.passed) {
    await mkdir("salidas", { recursive: true });
    const salida = {
      caso: CASO,
      unidades_cargadas: [...idsCargados],
      pasos: resultados.map((r) => ({
        agente: r.agente,
        permitido: r.verdicto.passed,
        razon: r.verdicto.reason,
      })),
      timestamp: new Date().toISOString(),
    };
    const destino = path.join("salidas", "resultado.json");
    await writeFile(destino, JSON.stringify(salida, null, 2));
    console.log(`  escrito: ${destino}`);
  } else {
    console.log("  NO se escribió nada — la acción del executor fue denegada por kcp-harness.");
    console.log("  Esto es exactamente lo que 'Out of Bounds' demuestra en pi-kcp: una llamada");
    console.log("  fuera de action_scope se bloquea con una razón escrita, no se ignora.");
  }

  console.log("\nResumen:");
  console.log(`  unidades cargadas por kcp-agent: ${idsCargados.size}`);
  console.log(`  pasos permitidos:  ${resultados.filter((r) => r.verdicto.passed).length}/${resultados.length}`);
  console.log(`  pasos denegados:   ${resultados.filter((r) => !r.verdicto.passed).length}/${resultados.length}`);
}

main().catch((err: unknown) => {
  const message = err instanceof Error ? err.message : String(err);
  console.error("Error:", message);
  process.exit(1);
});
