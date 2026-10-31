"""Offline, seeded simulation used to measure anomaly detection against known injected faults.

Nothing here is part of the live app: no API route, database table or deployed model uses it, and
every number it produces is synthetic. Never present its results as real WASAC performance.

    config.py    the assumptions: distributions, fault rates, payment behaviour, the penalty
    generate.py  customers, monthly use, payment behaviour and injected faults
    ledger.py    the month-by-month billing state machine, and the CSV output
    detect.py    label-free features, the Isolation Forest and the rules, on test customers
    evaluate.py  precision, recall, F1, confidence intervals, seeds, blind spots and the figure
"""
