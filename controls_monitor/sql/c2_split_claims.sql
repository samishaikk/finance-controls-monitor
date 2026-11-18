WITH small AS (
    SELECT id, employee_id, amount, submitted_at
    FROM expenses
    WHERE amount < :approval_limit
      AND status <> 'rejected'
),
windows AS (
    SELECT
        a.id                                          AS anchor_id,
        a.employee_id                                 AS employee_id,
        a.submitted_at                                AS window_start,
        COUNT(*)                                      AS claim_count,
        SUM(b.amount)                                 AS total,
        array_agg(b.id ORDER BY b.submitted_at, b.id) AS claim_ids
    FROM small a
    JOIN small b
      ON b.employee_id = a.employee_id
     AND b.submitted_at >= a.submitted_at
     AND b.submitted_at <= a.submitted_at + make_interval(hours => :window_hours)
    GROUP BY a.id, a.employee_id, a.submitted_at
    HAVING COUNT(*) >= :min_claims
       AND SUM(b.amount) >= :approval_limit
)
SELECT DISTINCT ON (s.id)
    s.id            AS expense_id,
    s.employee_id   AS employee_id,
    s.amount        AS amount,
    w.claim_count   AS claim_count,
    w.total         AS total,
    w.claim_ids     AS claim_ids,
    w.window_start  AS window_start
FROM windows w
JOIN small s ON s.id = ANY (w.claim_ids)
ORDER BY s.id, w.total DESC, w.anchor_id;