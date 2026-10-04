"""
Test-run evidence / audit generator.

Each invocation runs the pytest suite and persists timestamped evidence so every
test session leaves a trace that can be attached to a report:

    reports/
      audit.log                      <- appended one line per run (audit trail)
      <YYYYmmdd_HHMMSS>/
        pytest-output.txt            <- full console output
        junit.xml                    <- machine-readable results
        summary.json                 <- counts + duration
        report.html                  <- human-readable report (screenshot me!)

Usage (from the project root, inside the venv):
    python scripts/test_audit.py
"""
import datetime
import html
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def _parse_junit(junit: Path):
    cases = []
    total = failures = errors = skipped = passed = 0
    duration = 0.0

    if not junit.exists():
        return cases, (total, passed, failures, errors, skipped, duration)

    root = ET.parse(junit).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    for suite in suites:
        duration += float(suite.get("time") or 0)
        for tc in suite.findall("testcase"):
            total += 1
            failure = tc.find("failure")
            error = tc.find("error")
            skip = tc.find("skipped")
            msg = ""
            if failure is not None:
                status, failures = "failed", failures + 1
                msg = failure.get("message") or ""
            elif error is not None:
                status, errors = "error", errors + 1
                msg = error.get("message") or ""
            elif skip is not None:
                status, skipped = "skipped", skipped + 1
            else:
                status, passed = "passed", passed + 1
            cases.append(
                {
                    "classname": tc.get("classname", ""),
                    "name": tc.get("name", ""),
                    "time": tc.get("time", "0"),
                    "status": status,
                    "message": msg.strip(),
                }
            )
    return cases, (total, passed, failures, errors, skipped, duration)


def _render_html(summary: dict, cases: list) -> str:
    ok = summary["failed"] == 0 and summary["errors"] == 0
    badge = "#16a34a" if ok else "#dc2626"
    verdict = "PASSED" if ok else "FAILED"
    color = {"passed": "#16a34a", "failed": "#dc2626", "error": "#b91c1c", "skipped": "#6b7280"}

    rows = []
    for c in cases:
        name = html.escape(f"{c['classname']}::{c['name']}")
        rows.append(
            f"<tr><td class='st' style='color:{color[c['status']]};font-weight:600'>"
            f"{c['status'].upper()}</td><td class='mono'>{name}</td>"
            f"<td class='num'>{c['time']}s</td></tr>"
        )
    rows_html = "\n".join(rows)

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<title>Báo cáo test - {summary['timestamp']}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background:#f1f5f9; color:#0f172a; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px 64px; }}
  header {{ background:#0f172a; color:#fff; border-radius:16px; padding:28px 32px; }}
  header h1 {{ margin:0 0 6px; font-size:24px; }}
  header .sub {{ color:#94a3b8; font-size:14px; }}
  .verdict {{ display:inline-block; margin-top:14px; padding:6px 16px; border-radius:999px;
              background:{badge}; color:#fff; font-weight:700; letter-spacing:.5px; }}
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin:20px 0; }}
  .card {{ background:#fff; border:1px solid #e2e8f0; border-radius:14px; padding:16px; }}
  .card .k {{ font-size:12px; text-transform:uppercase; color:#64748b; letter-spacing:.05em; }}
  .card .v {{ font-size:28px; font-weight:700; margin-top:6px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:14px; overflow:hidden;
           border:1px solid #e2e8f0; }}
  th, td {{ text-align:left; padding:10px 14px; border-bottom:1px solid #eef2f7; font-size:13px; }}
  th {{ background:#f8fafc; color:#475569; text-transform:uppercase; font-size:11px; letter-spacing:.05em; }}
  .mono {{ font-family: 'Consolas', monospace; }}
  .num {{ text-align:right; color:#64748b; }}
  tr:last-child td {{ border-bottom:none; }}
  footer {{ margin-top:18px; color:#64748b; font-size:12px; text-align:center; }}
</style></head>
<body><div class="wrap">
  <header>
    <h1>Báo cáo kiểm thử &amp; Audit bảo mật - Module 1 (Auth &amp; Security)</h1>
    <div class="sub">Thời điểm chạy: {summary['timestamp']} &nbsp;•&nbsp; Lệnh: python -m pytest -v</div>
    <div class="verdict">{verdict}</div>
  </header>
  <div class="cards">
    <div class="card"><div class="k">Tổng</div><div class="v">{summary['total']}</div></div>
    <div class="card"><div class="k">Passed</div><div class="v" style="color:#16a34a">{summary['passed']}</div></div>
    <div class="card"><div class="k">Failed</div><div class="v" style="color:#dc2626">{summary['failed']}</div></div>
    <div class="card"><div class="k">Errors</div><div class="v" style="color:#b91c1c">{summary['errors']}</div></div>
    <div class="card"><div class="k">Thời lượng</div><div class="v">{summary['duration_seconds']}s</div></div>
  </div>
  <table>
    <thead><tr><th>Trạng thái</th><th>Test case</th><th style="text-align:right">TG</th></tr></thead>
    <tbody>
{rows_html}
    </tbody>
  </table>
  <footer>Tạo tự động bởi scripts/test_audit.py • bằng chứng lưu tại reports/{summary['timestamp']}/</footer>
</div></body></html>
"""


def main() -> int:
    started = datetime.datetime.now()
    run_id = started.strftime("%Y%m%d_%H%M%S")
    run_dir = REPORTS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    junit = run_dir / "junit.xml"

    cmd = [sys.executable, "-m", "pytest", "-v", f"--junitxml={junit}"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    console = (proc.stdout or "") + "\n" + (proc.stderr or "")
    (run_dir / "pytest-output.txt").write_text(console, encoding="utf-8")
    print(console)

    cases, (total, passed, failures, errors, skipped, duration) = _parse_junit(junit)
    summary = {
        "run_id": run_id,
        "timestamp": started.strftime("%Y-%m-%d %H:%M:%S"),
        "command": "python -m pytest -v",
        "returncode": proc.returncode,
        "total": total,
        "passed": passed,
        "failed": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": round(duration, 2),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "report.html").write_text(_render_html(summary, cases), encoding="utf-8")

    REPORTS.mkdir(parents=True, exist_ok=True)
    with (REPORTS / "audit.log").open("a", encoding="utf-8") as log:
        log.write(
            f"{datetime.datetime.now().isoformat(timespec='seconds')} | run={run_id} | "
            f"total={total} passed={passed} failed={failures} errors={errors} skipped={skipped} | "
            f"rc={proc.returncode}\n"
        )

    print("=" * 70)
    print(f" EVIDENCE -> {run_dir}")
    print(f"   report.html | summary.json | junit.xml | pytest-output.txt")
    print("=" * 70)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
