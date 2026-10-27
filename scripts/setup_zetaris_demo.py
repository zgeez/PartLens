"""Register the approved internal demo in the owner's running local Zetaris Docker instance.

Creates a fresh namespace and copies only the approved BOM and existing supplier fixture. No downloads,
credentials, production data or existing tables are modified. Export alone is not integration success:
the script requires Zetaris queries to return the expected counts and a real BOM/supplier join.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from partlens.cli import load_env_file
from partlens.core.bom import import_bom_csv
from partlens.demo import DEMO_BOM
from partlens.records import RunRecorder
from partlens.sources.catalog import FLAT_COLUMNS
from partlens.sources.zetaris import ZetarisClient, ZetarisConfig


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", required=True, type=Path, help="existing timestamped internal JSON fixture")
    ap.add_argument("--base-url", help="authorized UI gateway origin; defaults to ZETARIS_BASE_URL")
    ap.add_argument("--container", default="zetaris-driver-1", help="owner's local Zetaris driver container")
    ap.add_argument("--container-data-root", default="/home/zetaris/customer-data/shared",
                    help="container's configured ZETARIS_LOCAL_FILE_SYTEM_ROOT_PATH")
    args = ap.parse_args()
    load_env_file()
    rec = RunRecorder.create(Path(".partlens/runs"))
    print(f"Record: {rec.path}", flush=True)
    try:
        cfg = ZetarisConfig.from_env()
        if cfg is None:
            raise ValueError("authorized Zetaris credentials are not configured")
        if args.base_url:
            cfg.base_url = args.base_url
        client = ZetarisClient(cfg, recorder=rec)
        if any(p.casefold() == "experiments" or "benchmark" in p.casefold() or "badge" in p.casefold()
               for p in args.catalog.resolve().parts):
            raise ValueError("excluded private material cannot be imported")
        raw = args.catalog.read_bytes()
        rows = json.loads(raw)
        bom = import_bom_csv(DEMO_BOM)
        if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
            raise ValueError("catalog must be a nonempty list of rows")
        part_ids = [str(r.get("supplier", "")).lower() + ":" + str(r.get("supplier_pn", "")) for r in rows]
        if len(set(part_ids)) != len(part_ids):
            raise ValueError("duplicate supplier identifiers in catalog")
        namespace = "PARTLENS_EASYDUINO_" + rec.run_id.replace("-", "_")
        target = Path(".partlens/zetaris") / ("partlens-" + rec.run_id)
        target.mkdir(parents=True, exist_ok=False)
        # Keep nested catalog fields as JSON strings, matching the flat catalogue contract.
        flat = []
        for row in rows:
            item = {k: row.get(k) for k in FLAT_COLUMNS}
            for k, default in (("params", {}), ("price_breaks", []), ("alternates", [])):
                item[k] = json.dumps(row.get(k) or default, ensure_ascii=False) if not isinstance(
                    row.get(k), str) else row[k]
            flat.append(item)
        placed = {ln.id for ln in bom.placed_lines}
        bom_rows = [{"line_id": ln.id, "refs": ",".join(ln.refs), "qty_per_board": ln.qty_per_board,
                     "supplier": "lcsc", "supplier_pn": ln.supplier_pn, "value": ln.value,
                     "footprint": ln.footprint, "placed": ln.id in placed} for ln in bom.lines]
        for name, values in (("parts", flat), ("bom", bom_rows)):
            # This gateway's JSON source reads one document, so export an array rather than JSON Lines.
            (target / f"{name}.json").write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.iterdir())}
        rec.log("zetaris_demo_export", fixture_path=str(args.catalog),
                fixture_sha256=hashlib.sha256(raw).hexdigest(), bom_path=str(DEMO_BOM),
                bom_sha256=hashlib.sha256(Path(DEMO_BOM).read_bytes()).hexdigest(),
                supplier_rows=len(rows), bom_rows=len(bom_rows), exports=hashes,
                internal_only=True, live_supplier_refresh=False)
        # File registration is restricted to the configured storage root, shared by API and driver.
        if not args.container_data_root.startswith("/") or ".." in args.container_data_root.split("/"):
            raise ValueError("container data root must be an absolute path without parent traversal")
        container_dir = args.container_data_root.rstrip("/") + "/" + target.name
        result = subprocess.run(["docker", "cp", str(target.resolve()), args.container + ":" + container_dir],
                                capture_output=True)
        rec.log("zetaris_demo_copy", container=args.container, destination=container_dir,
                exit_code=result.returncode, files=hashes)
        if result.returncode:
            raise RuntimeError("Docker copy failed; check local container access")
        result = subprocess.run(["docker", "exec", args.container, "sha256sum",
                                 container_dir + "/bom.json", container_dir + "/parts.json"], capture_output=True)
        remote = dict((Path(name).name, sha) for sha, name in
                      (line.split(None, 1) for line in result.stdout.decode().splitlines()))
        if result.returncode or remote != hashes:
            raise RuntimeError("container export hashes did not match local files")
        rec.log("zetaris_demo_copy_verified", container=args.container, hashes=remote)
        statements = [f'CREATE LIGHTNING DATABASE {namespace} DESCRIBE BY "PartLens approved internal Easyduino demo"']
        statements += [f'CREATE LIGHTNING FILESTORE TABLE {name} FROM {namespace} FORMAT JSON '
                       f'OPTIONS (path "{container_dir}/{name}.json", multiLine "true")'
                       for name in ("parts", "bom")]
        statements += [f"SELECT COUNT(*) AS row_count FROM {namespace}.parts",
                       f"SELECT COUNT(*) AS row_count FROM {namespace}.bom"]
        counts = []
        for sql in statements:
            values, query = client.query(sql)
            rec.log("zetaris_demo_result", sql=sql, query_request_id=query.request_id, rows=values)
            if values and "row_count" in values[0]:
                counts.append(int(values[0]["row_count"]))
            print(f"Zetaris succeeded: {sql}", flush=True)
        if counts != [len(rows), len(bom_rows)]:
            raise RuntimeError("Zetaris row counts differ from the exported dataset")
        sql = (f"SELECT b.line_id, b.refs, b.qty_per_board, p.supplier, p.supplier_pn, p.mpn, "
               f"p.stock, p.retrieved_at FROM {namespace}.bom b LEFT JOIN {namespace}.parts p "
               "ON b.supplier = p.supplier AND b.supplier_pn = p.supplier_pn "
               "WHERE b.placed = true ORDER BY b.line_id")
        values, query = client.query(sql)
        expected = {ln.id for ln in bom.placed_lines if "lcsc:" + str(ln.supplier_pn) in part_ids}
        matched = {r["line_id"] for r in values if r.get("supplier_pn")}
        valid = len(values) == len(bom.placed_lines) and matched == expected and bool(matched)
        rec.log("zetaris_dataset_evidence", query_request_id=query.request_id, rows=values,
                matched_bom_lines=sorted(matched), expected_bom_lines=sorted(expected),
                demo_dataset_verified=valid, namespace=namespace, parts_table=namespace + ".parts")
        if not valid:
            raise RuntimeError("Zetaris BOM/supplier join did not match the approved dataset")
        manifest = {"namespace": namespace, "parts_table": namespace + ".parts", "bom_table": namespace + ".bom",
                    "record": str(rec.path), "container": args.container, "container_path": container_dir,
                    "base_url": cfg.base_url, "supplier_rows": len(rows), "bom_rows": len(bom_rows),
                    "placed_lines": len(values), "matched_lines": len(matched), "hashes": hashes}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))
        return 0
    except Exception as exc:
        # Query failures have sanitized transport evidence in their own events; no raw server bodies/keys.
        rec.log("zetaris_demo_setup_failed", error_type=type(exc).__name__, error=str(exc))
        print(f"Setup failed ({type(exc).__name__}); see {rec.path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
