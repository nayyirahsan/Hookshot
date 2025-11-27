"""Delivery-side metrics for the k6 load test, computed from the database.

Run after the retry queue drains: python -m load_test.report
"""

from sqlalchemy import text

from api.database import SyncSessionLocal

QUERY = text(
    """
    WITH firsts AS (
        SELECT
            e.event_type,
            e.id AS event_id,
            MIN(da.attempted_at) FILTER (WHERE da.outcome = 'success') AS first_success,
            e.created_at,
            COUNT(da.id) AS attempts
        FROM events e
        JOIN delivery_attempts da ON da.event_id = e.id
        WHERE e.event_type LIKE 'load.%'
        GROUP BY e.event_type, e.id, e.created_at
    )
    SELECT
        event_type,
        COUNT(*) AS events,
        COUNT(first_success) AS delivered,
        ROUND(100.0 * COUNT(first_success) / COUNT(*), 2) AS delivered_pct,
        ROUND(AVG(EXTRACT(EPOCH FROM (first_success - created_at)))::numeric, 3)
            AS mean_delivery_latency_s,
        ROUND((PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (first_success - created_at))))::numeric, 3)
            AS p50_delivery_latency_s,
        ROUND((PERCENTILE_CONT(0.95) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM (first_success - created_at))))::numeric, 3)
            AS p95_delivery_latency_s,
        ROUND(AVG(attempts), 2) AS mean_attempts
    FROM firsts
    GROUP BY event_type
    ORDER BY event_type
    """
)

PENDING = text(
    """
    SELECT COUNT(*) FROM events e
    WHERE e.event_type LIKE 'load.%'
      AND NOT EXISTS (
        SELECT 1 FROM delivery_attempts da
        WHERE da.event_id = e.id AND da.outcome = 'success')
      AND NOT EXISTS (
        SELECT 1 FROM dead_letters dl WHERE dl.event_id = e.id)
    """
)


def main() -> None:
    with SyncSessionLocal() as db:
        pending = db.execute(PENDING).scalar_one()
        rows = db.execute(QUERY).all()

    print(f"{'class':<16} {'events':>7} {'delivered':>10} {'mean lat':>9} "
          f"{'p50':>7} {'p95':>8} {'attempts':>9}")
    for row in rows:
        print(f"{row.event_type:<16} {row.events:>7} {row.delivered_pct:>9}% "
              f"{row.mean_delivery_latency_s:>8}s {row.p50_delivery_latency_s:>6}s "
              f"{row.p95_delivery_latency_s:>7}s {row.mean_attempts:>9}")
    print(f"\nstill pending (no success, not dead-lettered): {pending}")


if __name__ == "__main__":
    main()
