"""Run the whole offline simulation: data, billing, detection and evaluation (synthetic data only).

    python scripts/run_simulation.py                          # 500 customers, 12 months, seed 42
    python scripts/run_simulation.py --seed 7 --customers 100
    python scripts/run_simulation.py --seeds 5 --bootstrap 500  # faster

Writes CSV files, metrics.json and confusion_matrices.png to backend/simulation/output/ (gitignored).
Touches no database. The figure needs matplotlib (requirements-dev.txt).
"""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation.config import DEFAULT_OUTPUT_DIR, SimulationConfig  # noqa: E402
from simulation.detect import run_detection, write_detections  # noqa: E402
from simulation.evaluate import (  # noqa: E402
    N_BOOTSTRAP, N_SEEDS, NOTICE, SETUP_TITLES, SETUPS, build_report, write_confusion_plot, write_metrics,
)
from simulation.ledger import State, run_simulation, write_outputs  # noqa: E402


def _print_setups(report: dict) -> None:
    for setup in SETUPS:
        data = report["setups"][setup]
        line = "  ".join(
            f"{name} {data[name]['value']:.3f} [{data[name]['ci_low']:.3f}, {data[name]['ci_high']:.3f}]"
            for name in ("precision", "recall", "f1")
        )
        print(f"  {SETUP_TITLES[setup]:<15} {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    defaults = SimulationConfig()
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--customers", type=int, default=defaults.n_customers)
    parser.add_argument("--months", type=int, default=defaults.n_months)
    parser.add_argument("--bootstrap", type=int, default=N_BOOTSTRAP, help="Resamples for the 95%% intervals")
    parser.add_argument("--seeds", type=int, default=N_SEEDS, help="Extra seeds for the stability check")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    config = replace(defaults, seed=args.seed, n_customers=args.customers, n_months=args.months)
    simulation = run_simulation(config)
    paths = write_outputs(simulation, args.output)

    active = sum(1 for row in simulation.ledger if row.state == State.ACTIVE.value)
    labelled = sum(row.ground_truth_anomaly for row in simulation.ledger)
    print(NOTICE)
    print(f"Customers: {len(simulation.customers)}, ledger rows: {len(simulation.ledger)}, active months: {active}")
    print(f"Fault events: {len(simulation.events)}, fault months: {labelled} ({labelled / active:.2%} of active)")

    result = run_detection(simulation)
    paths.append(write_detections(result.detections, args.output))
    print(f"Trained on {result.model.n_samples} months from {len(result.train_customers)} customers")

    report = build_report(simulation, result, args.bootstrap, args.seeds,
                          on_seed=lambda seed: print(f"  seed {seed} done", flush=True))
    paths.append(write_metrics(report, args.output))
    paths.append(write_confusion_plot(report, args.output))

    print(f"Test set: {report['test_months']} months, {report['fault_months']} faults. Value [95% interval]:")
    _print_setups(report)
    print("Subtle faults:")
    _print_setups(report["subtle_faults"])
    for path in paths:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
