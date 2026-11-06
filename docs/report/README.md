# Technical report

The editable source is `technical_report.html`. The checked-in PDF is rebuilt from it.

From the repository root, with a Python environment active:

```sh
pip install -r docs/report/requirements.txt
python backend/scripts/render_report.py
```

The portable ReportLab renderer preserves the report text, tables, figures and architecture diagram;
layout is deliberately compact and is checked in CI to remain at five pages or fewer. The current
report has four pages. `tools/e2e/render_report.mjs` is an alternative Chromium renderer when browser
execution is available; install `tools/e2e` dependencies and Chromium first.

The local tests and the Linux Docker/browser evidence are dated in `docs/testing/`. Pilot results,
provider delivery and independent security validation are not claimed.
