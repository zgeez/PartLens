"""Bounded read-only demo checks. Availability is separate from agent or engineering success."""
from pathlib import Path

from .records import RunRecorder


def service_checks(state, recorder):
    def ollama():
        from .local_provider import OllamaProvider
        provider = OllamaProvider()
        provider._inspect()
        version = provider._request('/api/version').get('version')
        return {'model': provider.model, 'protocol': provider.protocol, 'runtime_version': version,
                'metadata': provider.metadata, 'inference_performed': False}

    def jlcpcb():
        from .sources.jlcpcb import JLCClient, JLCConfig, row_from_detail
        cfg = JLCConfig.from_env()
        if cfg is None:raise ValueError('missing configuration')
        result = JLCClient(cfg, recorder=recorder, cache_dir=state/'jlcpcb/cache', attempts=1).lookup(['C1525'], refresh=True)
        matched = [row_from_detail(r, result) for r in result.data if r.get('componentCode') == 'C1525']
        if not matched:raise ValueError('approved demo component absent')
        return {'http_status': result.http_status, 'cached': result.cached, 'queried_at': result.retrieved_at,
                'client_request_id': result.request_id, 'server_trace_id': result.trace_id,
                'source': result.source, 'response_digest': result.response_digest, 'matched_codes': ['C1525']}

    def zetaris():
        from .core.bom import import_bom_csv
        from .demo import DEMO_BOM
        from .sources.zetaris import ZetarisClient, ZetarisConfig, IDENT
        from .core.model import to_jsonable
        cfg = ZetarisConfig.from_env()
        if cfg is None or not cfg.parts_table or not IDENT.fullmatch(cfg.parts_table):raise ValueError('missing configuration')
        codes = sorted({r.supplier_pn for r in import_bom_csv(DEMO_BOM).placed_lines if r.supplier_pn})
        sql = f"SELECT supplier_pn FROM {cfg.parts_table} WHERE supplier_pn IN (" + ','.join("'"+c+"'" for c in codes) + ') LIMIT 5'
        rows, query = ZetarisClient(cfg, recorder=recorder).query(sql, limit=5)
        matches = [v for r in rows for k,v in r.items() if k.lower() == 'supplier_pn' and v in codes]
        if not matches:raise ValueError('demo dataset not verified')
        return {'query': to_jsonable(query), 'demo_dataset_verified': True, 'matching_rows': len(matches)}

    def meterless():
        from .memory.hmem import HMemBridge
        with HMemBridge(state/'preflight-memory'/recorder.run_id) as bridge:
            return {'hello': bridge.info, 'stats': bridge.call('stats'), 'scope': 'bridge operation; no agent recall claim'}

    return {'ollama': ollama, 'jlcpcb': jlcpcb, 'zetaris': zetaris, 'meterless': meterless}


def run_preflight(state=Path('.partlens'), *, checks=None):
    """Attempt every check, including after a failure; never emit credentials or raw supplier records."""
    state = Path(state)
    rec = RunRecorder.create(state/'preflight')
    actions = {
        'ollama': 'Start loopback Ollama and install the selected local model; check PARTLENS_LOCAL_PROTOCOL.',
        'jlcpcb': 'Check owner-local JLC_APP_ID, JLC_ACCESS_KEY, JLC_SECRET_KEY and official API connectivity.',
        'zetaris': 'Check owner-local ZETARIS_* and PARTLENS_ZETARIS_PARTS_TABLE; start the existing deployment/driver.',
        'meterless': 'Install Node 20+, run npm ci and npm run setup in integrations/hmem-bridge.',
    }
    results = {}
    for name, check in (checks if checks is not None else service_checks(state, rec)).items():
        try:
            results[name] = {'available': True, 'evidence': check()}
        except Exception as exc:
            # Exception bodies can contain tokens/URLs. The adapters journal sanitized operation evidence.
            results[name] = {'available': False, 'error_type': type(exc).__name__, 'action': actions[name]}
        rec.log('service_check', service=name, **results[name])
    ready = len(results) == 4 and all(r['available'] for r in results.values())
    report = {'services_available': ready, 'checks': results, 'record': str(rec.path),
              'scope': 'startup observations only; no model execution, engineering acceptance or future-uptime guarantee'}
    rec.log('preflight_result', report=report)
    return report
