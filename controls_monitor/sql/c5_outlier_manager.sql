
WITH decisions AS (
    SELECT
        approver_id,
        COUNT(*)                                        AS decisions,
        COUNT(*) FILTER (WHERE status = 'approved')     AS approved,
        ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'approved') / COUNT(*), 1)
                                                        AS approval_rate
    FROM expenses
    WHERE approver_id IS NOT NULL
      AND status IN ('approved', 'rejected')
    GROUP BY approver_id
    HAVING COUNT(*) >= :min_decisions
),
scored AS (
    SELECT
        d.*,
        (SELECT COUNT(*) FROM decisions p
          WHERE p.approver_id <> d.approver_id)         AS peer_count,
        (SELECT ROUND(CAST(percentile_cont(0.5) WITHIN GROUP (ORDER BY p.approval_rate) AS numeric), 1)
           FROM decisions p
          WHERE p.approver_id <> d.approver_id)         AS peer_median
    FROM decisions d
)
SELECT
    approver_id                         AS employee_id,
    decisions,
    approved,
    approval_rate,
    peer_median,
    peer_count,
    approval_rate - peer_median         AS gap_points
FROM scored
WHERE peer_count >= 2
  AND approval_rate - peer_median >= :min_rate_gap_points
ORDER BY approver_id;