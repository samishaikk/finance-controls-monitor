SELECT
    x.id            AS expense_id,
    x.employee_id   AS employee_id,
    x.approver_id   AS approver_id,
    x.amount        AS amount,
    x.submitted_at  AS submitted_at,
    x.approved_at   AS approved_at,
    CAST(FLOOR(EXTRACT(EPOCH FROM (x.approved_at - x.submitted_at))) AS integer)
                    AS latency_seconds
FROM expenses x
WHERE x.status = 'approved'
  AND x.approved_at IS NOT NULL
  AND x.approved_at - x.submitted_at < make_interval(secs => :min_review_seconds)
ORDER BY x.id;