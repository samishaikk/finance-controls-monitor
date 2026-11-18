
SELECT DISTINCT ON (b.id)
    b.id                AS expense_id,
    b.employee_id       AS employee_id,
    a.id                AS original_expense_id,
    CASE
        WHEN a.receipt_number IS NOT NULL
         AND a.receipt_number = b.receipt_number THEN 'same_receipt'
        ELSE 'same_employee_vendor_amount'
    END                 AS match_type,
    b.vendor            AS vendor,
    b.amount            AS amount,
    a.submitted_at      AS original_submitted_at,
    b.submitted_at      AS submitted_at
FROM expenses a
JOIN expenses b
  ON (a.submitted_at, a.id) < (b.submitted_at, b.id)
 AND a.status <> 'rejected'
 AND b.status <> 'rejected'
 AND (
        (a.receipt_number IS NOT NULL AND a.receipt_number = b.receipt_number)
     OR (    a.employee_id = b.employee_id
         AND a.vendor = b.vendor
         AND a.amount = b.amount
         AND b.submitted_at - a.submitted_at <= make_interval(days => :window_days))
     )
ORDER BY b.id, a.submitted_at, a.id;