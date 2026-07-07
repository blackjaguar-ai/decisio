"""
Test de los 4 caminos — Día 10.
Verifica que cada path del grafo funciona end-to-end.
Requiere servidor corriendo: PYTHONPATH=. uvicorn app.main:app --reload
"""

import asyncio
import sys
import httpx

BASE_URL = "http://localhost:8000"

CASES = {
    "clean_approval_1": {
        "customer_id": "CLI-001", "name": "Ana Torres Quispe",
        "credit_score": 780, "tenure_months": 24, "dti_ratio": 0.22,
        "max_days_overdue_12m": 0, "requested_amount": 8000.0, "preapproved_limit": 12000.0,
        "monthly_income": 5500.0,
    },
    "gray_zone_1": {
        "customer_id": "CLI-003", "name": "Carmen Flores Medina",
        "credit_score": 670, "tenure_months": 9, "dti_ratio": 0.44,
        "max_days_overdue_12m": 15, "requested_amount": 6000.0, "preapproved_limit": 8000.0,
        "monthly_income": 3800.0,
    },
    "high_amount": {
        "customer_id": "CLI-005", "name": "Patricia Mendoza Lagos",
        "credit_score": 810, "tenure_months": 36, "dti_ratio": 0.18,
        "max_days_overdue_12m": 0, "requested_amount": 15000.0, "preapproved_limit": 12000.0,
        "monthly_income": 8000.0,
    },
    "hard_rejection": {
        "customer_id": "CLI-006", "name": "Luis Romero Pizarro",
        "credit_score": 580, "tenure_months": 3, "dti_ratio": 0.62,
        "max_days_overdue_12m": 45, "requested_amount": 4000.0, "preapproved_limit": 5000.0,
        "monthly_income": 2200.0,
    },
}

EXPECTED = {
    "clean_approval_1": "approved",
    "gray_zone_1":      "pending_human",
    "high_amount":      "pending_human",
    "hard_rejection":   "rejected",
}


async def test_case(client: httpx.AsyncClient, name: str, customer: dict) -> bool:
    print(f"\n{'─'*55}")
    print(f"  {name}")
    print(f"  Esperado: {EXPECTED[name]}")

    try:
        r = await client.post(f"{BASE_URL}/decision", json={"customer": customer}, timeout=30.0)
        r.raise_for_status()
        data = r.json()

        outcome    = data.get("outcome")
        latency    = data.get("latency_ms")
        route      = data.get("route")
        summary    = data.get("explanation", {}).get("summary", "")[:90]
        flags      = data.get("guardrail_flags", [])

        print(f"  Resultado : {outcome}")
        print(f"  Route     : {route} | Latencia: {latency}ms")
        print(f"  Explicación: {summary}...")
        if flags:
            print(f"  Guardrails: {[f['guardrail'] for f in flags]}")

        passed = outcome == EXPECTED[name]
        print(f"  {'✓ PASS' if passed else '✗ FAIL — esperado: ' + EXPECTED[name]}")
        return passed

    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False


async def main():
    print("=" * 55)
    print("  DECISIO — Test 4 Caminos | Semana 1 Día 10")
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

        # 2. Los 4 caminos
        results = []
        for name, customer in CASES.items():
            results.append(await test_case(client, name, customer))

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
