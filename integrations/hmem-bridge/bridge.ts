// JSON-lines bridge to the Meterless H-MEM reference engine.
//
// One request per stdin line: {"id": 1, "op": "add", "args": {...}}
// One response per stdout line: {"id": 1, "ok": true, "result": ...} or {"id": 1, "ok": false, "error": "..."}
//
// The engine runs with persistDir, so state.json and the append-only ledger.jsonl survive restarts.
// Embeddings are stripped from responses (they are engine-internal).

import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { fileURLToPath, pathToFileURL } from "node:url";
import { HMEM } from "./vendor/hmem/src/index.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const entry = path.join(here, "vendor", "hmem", "src", "index.ts");

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : undefined;
}

function strip(rec: any): any {
  if (!rec) return rec;
  const { embedding, ...rest } = rec;
  return rest;
}

async function main(): Promise<void> {
  if (!process.argv.includes('--bundled') && !fs.existsSync(entry)) {
    process.stderr.write("H-MEM engine not vendored. Run `npm run setup` in integrations/hmem-bridge.\n");
    process.exit(2);
  }
  const persistDir = arg("persist-dir");
  if (!persistDir) {
    process.stderr.write("usage: tsx bridge.ts --persist-dir DIR [--actor NAME] [--clock-ms N]\n");
    process.exit(2);
  }
  const fixedClock = arg("clock-ms");
  const hmem = new HMEM({
    persistDir,
    actor: arg("actor") ?? "partlens",
    clock: fixedClock ? () => Number(fixedClock) : Date.now,
  });

  const ops: Record<string, (a: any) => unknown> = {
    hello: () => ({ engine: "meterless-hmem-reference", entry: process.argv.includes('--bundled') ? 'bundled-hmem@1742dec56a66e58eef9dda2d2b865823758ca8cd' : path.relative(here, entry), persistDir }),
    add: (a) => strip(hmem.add(a)),
    get: (a) => strip(hmem.store.get(a.id)) ?? null,
    query: (a) => {
      const r = hmem.query(a.query, { topN: a.topN, threshold: a.threshold });
      return { ...r, memories: r.memories.map((m: any) => ({ memory: strip(m.memory), relevance: m.relevance })) };
    },
    // Exact tag lookup over the store. Reads are written to the ledger like retrieval reads.
    find_by_tags: (a) => {
      const want: string[] = a.tags ?? [];
      const hits = hmem.store
        .all()
        .filter((m: any) => want.every((t) => m.tags.includes(t)))
        .sort((x: any, y: any) => x.id.localeCompare(y.id));
      for (const m of hits) hmem.ledger.log(m.id, "read", "partlens", { details: { find_by_tags: want } });
      return hits.map(strip);
    },
    feedback: (a) => {
      hmem.feedback(a.id, a.kind);
      return strip(hmem.store.get(a.id));
    },
    history: (a) => hmem.ledger.history(a.id),
    stats: () => ({ records: hmem.store.all().length, ledger: hmem.ledger.stats() }),
  };

  const rl = readline.createInterface({ input: process.stdin });
  for await (const line of rl) {
    if (!line.trim()) continue;
    let id: unknown = null;
    try {
      const req = JSON.parse(line);
      id = req.id;
      const fn = ops[req.op];
      if (!fn) throw new Error(`unknown op ${req.op}`);
      const result = await fn(req.args ?? {});
      process.stdout.write(JSON.stringify({ id, ok: true, result }) + "\n");
    } catch (e: any) {
      process.stdout.write(JSON.stringify({ id, ok: false, error: String(e?.message ?? e) }) + "\n");
    }
  }
}

main();
