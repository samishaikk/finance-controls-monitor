WITH approvals AS (
    SELECT
        x.id,
        x.employee_id,
        x.approver_id,
        x.amount,
        x.approved_at,
        CAST(EXTRACT(ISODOW FROM x.approved_at AT TIME ZONE 'UTC') AS integer) AS iso_weekday,
        CAST(EXTRACT(HOUR   FROM x.approved_at AT TIME ZONE 'UTC') AS integer) AS hour_utc
    FROM expenses x
    WHERE x.status = 'approved'
      AND x.approved_at IS NOT NULL
)
SELECT
    id            AS expense_id,
    employee_id,
    approver_id,
    amount,
    approved_at,
    iso_weekday,
    hour_utc,
    CASE
        WHEN :flag_weekends AND iso_weekday IN (6, 7) THEN 'weekend'
        ELSE 'off_hours'
    END           AS reason_type
FROM approvals
WHERE (:flag_weekends AND iso_weekday IN (6, 7))
   OR hour_utc < :business_start_hour
   OR hour_utc >= :business_end_hour
ORDER BY id;