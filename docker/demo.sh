set -u
echo "== waiting for the database"
python - <<'PY'
import sys, time
from sqlalchemy import text
from controls_monitor.db import make_engine

engine = make_engine()
for attempt in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("database is ready")
        sys.exit(0)
    except Exception as exc:
        print(f"  not ready yet ({attempt + 1}/30): {type(exc).__name__}")
        time.sleep(2)
print("database never became ready", file=sys.stderr)
sys.exit(1)
PY
[ $? -eq 0 ] || exit 1

mkdir -p reports

echo
echo "== 1/3 seed a synthetic company and plant known violations"
python -m controls_monitor.generator --reset --with-violations || exit 1

echo
echo "== 2/3 score the controls against the planted cases"
python -m controls_monitor evaluate --output reports/evaluation.md || exit 1

echo
echo "== 3/3 run the monitor like a scheduled job (exit code 1 is expected here)"
python -m controls_monitor run --report reports/latest.md --metrics reports/controls_monitor.prom 2>reports/run.log
code=$?
echo "monitor exit code: $code  (0 = clean, 1 = exceptions at or above fail level, 2 = crash)"
echo "structured logs: reports/run.log ($(wc -l < reports/run.log) JSON lines)"

echo
echo "== done - open reports/latest.md and reports/evaluation.md"
[ "$code" -le 1 ] || exit "$code"