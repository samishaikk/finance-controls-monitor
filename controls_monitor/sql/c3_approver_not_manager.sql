SELECT
    x.id            AS expense_id,
    x.employee_id   AS employee_id,
    x.approver_id   AS approver_id,
    e.manager_id    AS manager_id,
    m.manager_id    AS skip_level_id,
    x.amount        AS amount,
    x.approved_at   AS approved_at,
    CASE
        WHEN x.approver_id IS NULL            THEN 'no_approver'
        WHEN x.approver_id = x.employee_id    THEN 'self_approval'
        ELSE 'not_manager'
    END             AS violation_type
FROM expenses x
JOIN employees e ON e.id = x.employee_id
LEFT JOIN employees m ON m.id = e.manager_id
WHERE x.status = 'approved'
  AND (
        x.approver_id IS NULL
     OR x.approver_id = x.employee_id
     OR (
            x.approver_id IS DISTINCT FROM e.manager_id
        AND NOT (
                 :allow_skip_level
             AND m.manager_id IS NOT NULL
             AND x.approver_id = m.manager_id
            )
        )
      )
ORDER BY x.id;