"""
Test de las 3 rutas reales + gate de identidad.
Consume data/profiles.py directamente — cero duplicación de payloads.
Requiere servidor corriendo: PYTHONPATH=. uvicorn app.main:app --reload
"""

import asyncio
import sys
import httpx

sys.path.insert(0, ".")
from data.profiles import PROFILES

BASE_URL = "http://localhost:8000"

EXPECTED = {
    "clean_approval_1":              "honored",
    "clean_approval_2_pinned_policy": "honored",
    "gray_zone_dti":                 "pending_human",
    "gray_zone_mora":                "pending_human",
    "hard_rejection_score_drop":     "revoked",
    "identity_mismatch":             "identity_verification_failed",
    "staleness_amount":              "pending_human",  # guardrail de staleness fuerza a humano
    "anomalous_inputs":              "pending_human",
}


async def test_case(client: httpx.AsyncClient, name: str, payload: dict) -> bool:
    print(f"\n{'─'*55}")
    print(f"  {name}")
    print(f"  Esperado: {EXPECTED[name]}")

    try:
        r = await client.post(f"{BASE_URL}/decision", json=payload, timeout=30.0)
        r.raise_for_status()
        data = r.json()

        outcome     = data.get("outcome")
        notice_type = data.get("notice_type")
        latency     = data.get("latency_ms")
        route       = data.get("route")
        summary     = data.get("explanation", {}).get("summary", "")[:90]
        flags       = data.get("guardrail_flags", [])

        print(f"  Resultado   : {outcome} | notice_type: {notice_type}")
        print(f"  Route       : {route} | Latencia: {latency}ms")
        print(f"  Explicación : {summary}...")
        if flags:
            print(f"  Guardrails  : {[f['guardrail'] for f in flags]}")

        passed = outcome == EXPECTED[name]
        print(f"  {'✓ PASS' if passed else '✗ FAIL — esperado: ' + EXPECTED[name]}")
        return passed

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False


async def main():
    print("=" * 55)
    print("  DECISIO — Test de rutas | revalidación de oferta firme")
    print("=" * 55)

    async with httpx.AsyncClient() as client:

        # 1. Healthcheck
        try:
            r = await client.get(f"{BASE_URL}/health", timeout=5.0)
            r.raise_for_status()
            print(f"\n  ✓ Servidor online: {r.json()}")
        except Exception as e:
            print(f"\n  ✗ Servidor offline: {e}")
            print("  Ejecutar: PYTHONPATH=. uvicorn app.main:app --reload")
            sys.exit(1)

        # 2. Todos los perfiles curados
        results = []
        for name, payload in PROFILES.items():
            results.append(await test_case(client, name, payload))

        # 3. Métricas
        try:
            r = await client.get(f"{BASE_URL}/metrics")
            m = r.json()
            print(f"\n{'─'*55}")
            print(f"  Métricas acumuladas:")
            print(f"  Total: {m['totals']['total']} | Distribución: {m['path_distribution']}")
            print(f"  Latencia promedio: {m['latency_ms']['avg']}ms")
        except Exception as e:
            print(f"  No se pudieron obtener métricas: {e}")

        print(f"\n{'='*55}")
        print(f"  RESULTADO: {sum(results)}/{len(results)} tests pasaron")
        print("=" * 55)

        if not all(results):
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
