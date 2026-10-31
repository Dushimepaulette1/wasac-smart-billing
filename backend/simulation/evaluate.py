"""Phase 4: how well each setup finds the injected faults. Synthetic data only.

Three setups are compared on test customers: the app's rules alone (what is live), the Isolation
Forest alone, and either of them flagging a month. This is the only module that joins detections to
the labels.

Confidence intervals resample whole customers, not months: a customer's months are not independent,
and a fault spans several of them, so resampling months would make the intervals too narrow. The same
resamples are used for every setup, so a difference between two setups has its own interval.

Three checks keep the headline honest:
    seed_study     repeats the whole simulation on other seeds, since one seed is one draw
    subtle_faults  repeats it with faults far smaller than the injected 3-5x and near-zero ones
    blind_spots    says what each setup missed and where its false alarms fell

The forest's contamination (0.05) equals the injected fault share. That is the app's default, but a
real fault rate is unknown, so this flatters the forest: stated with the results.
"""
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

from simulation.config import BYPASS, LEAK, FaultConfig, SimulationConfig
from simulation.detect import Detection, DetectionResult, run_detection
from simulation.ledger import NO_ANOMALY, Simulation, run_simulation

RULES = "rules"
FOREST = "forest"
COMBINED = "rules_plus_forest"
SETUPS = (RULES, FOREST, COMBINED)
SETUP_TITLES = {RULES: "Rules only", FOREST: "Forest only", COMBINED: "Rules + Forest"}
COMPARISONS = {"forest_minus_rules": (FOREST, RULES), "combined_minus_rules": (COMBINED, RULES)}
METRICS = ("precision", "recall", "f1", "false_alarm_rate")

N_BOOTSTRAP = 2000
N_SEEDS = 20
BOOTSTRAP_STREAM = 2  # with the seed: independent of the data and of the customer split
SUBTLE_FAULTS = FaultConfig(leak_multiplier=(1.5, 2.5), bypass_multiplier=(0.4, 0.6))
NOTICE = "Synthetic data. Not evidence of real WASAC performance."


@dataclass(frozen=True)
class Confusion:
    """Metrics with nothing to divide by are 0: a setup that flags nothing has no precision."""

    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        total = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / total if total else 0.0

    @property
    def false_alarm_rate(self) -> float:
        return self.fp / (self.fp + self.tn) if self.fp + self.tn else 0.0


@dataclass(frozen=True)
class ScoredMonth:
    customer_id: str
    customer_type: str
    month: int
    anomaly_type: str  # NO_ANOMALY, LEAK or BYPASS
    rule_flag: bool
    forest_flag: bool

    @property
    def is_fault(self) -> bool:
        return self.anomaly_type != NO_ANOMALY

    def flagged(self, setup: str) -> bool:
        if setup == RULES:
            return self.rule_flag
        if setup == FOREST:
            return self.forest_flag
        return self.rule_flag or self.forest_flag


def join_labels(simulation: Simulation, detections: Iterable[Detection]) -> List[ScoredMonth]:
    labels = {(r.customer_id, r.month): r.anomaly_type for r in simulation.ledger}
    kinds = {c.customer_id: c.customer_type for c in simulation.customers}
    return [
        ScoredMonth(d.customer_id, kinds[d.customer_id], d.month, labels[(d.customer_id, d.month)],
                    d.rule_flag, d.forest_flag)
        for d in detections
    ]


def confusion(months: Iterable[ScoredMonth], setup: str) -> Confusion:
    tp = fp = fn = tn = 0
    for month in months:
        flagged = month.flagged(setup)
        tp += month.is_fault and flagged
        fp += not month.is_fault and flagged
        fn += month.is_fault and not flagged
        tn += not month.is_fault and not flagged
    return Confusion(int(tp), int(fp), int(fn), int(tn))


def customer_counts(months: Sequence[ScoredMonth], customers: Sequence[str], setup: str) -> np.ndarray:
    """(tp, fp, fn, tn) per customer, in the order of customers."""
    index = {customer_id: i for i, customer_id in enumerate(customers)}
    counts = np.zeros((len(customers), 4), dtype=np.int64)
    for month in months:
        flagged = month.flagged(setup)
        column = (0 if flagged else 2) if month.is_fault else (1 if flagged else 3)
        counts[index[month.customer_id], column] += 1
    return counts


def _ratio(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    return np.divide(top, bottom, out=np.zeros_like(top, dtype=float), where=bottom > 0)


def metrics_from_totals(totals: np.ndarray) -> Dict[str, np.ndarray]:
    """The Confusion metrics for many (tp, fp, fn, tn) rows at once."""
    tp, fp, fn, tn = (totals[:, i].astype(float) for i in range(4))
    return {
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "false_alarm_rate": _ratio(fp, fp + tn),
    }


def bootstrap_draws(n_customers: int, n_bootstrap: int, seed: int) -> np.ndarray:
    return np.random.default_rng([seed, BOOTSTRAP_STREAM]).integers(0, n_customers, (n_bootstrap, n_customers))


def _interval(samples: np.ndarray) -> Dict[str, float]:
    low, high = np.percentile(samples, [2.5, 97.5])
    return {"ci_low": round(float(low), 4), "ci_high": round(float(high), 4)}


def _estimate(value: float, samples: np.ndarray) -> Dict[str, float]:
    return {"value": round(value, 4), **_interval(samples)}


def _recall_for(months: Sequence[ScoredMonth], customers: Sequence[str], setup: str, draws: np.ndarray) -> dict:
    counts = customer_counts(months, customers, setup)
    found = confusion(months, setup)
    samples = metrics_from_totals(counts[draws].sum(axis=1))["recall"]
    return {"caught": found.tp, "total": found.tp + found.fn, **_estimate(found.recall, samples)}


def detection_delay(months: Sequence[ScoredMonth], setup: str) -> dict:
    """For each fault, how many fault months passed before the first flag (0: its first month)."""
    faults: Dict[str, List[ScoredMonth]] = {}
    for month in months:
        if month.is_fault:
            faults.setdefault(month.customer_id, []).append(month)
    delays = []
    for rows in faults.values():
        flags = [m.flagged(setup) for m in sorted(rows, key=lambda m: m.month)]
        if any(flags):
            delays.append(flags.index(True))
    return {
        "faults": len(faults),
        "faults_caught": len(delays),
        "mean_fault_months_before_first_flag": round(mean(delays), 2) if delays else None,
    }


def blind_spots(months: Sequence[ScoredMonth], setup: str) -> dict:
    missed: Dict[str, int] = {}
    alarms: Dict[str, Dict[str, object]] = {}
    for kind in sorted({m.customer_type for m in months}):
        normal = [m for m in months if m.customer_type == kind and not m.is_fault]
        wrong = sum(m.flagged(setup) for m in normal)
        alarms[kind] = {
            "false_alarms": wrong, "normal_months": len(normal),
            "rate": round(wrong / len(normal), 4) if normal else 0.0,
        }
        for fault in (LEAK, BYPASS):
            missed[f"{kind}_{fault}"] = sum(
                m.customer_type == kind and m.anomaly_type == fault and not m.flagged(setup) for m in months
            )
    return {"missed_fault_months": missed, "false_alarms": alarms}


def evaluate_run(simulation: Simulation, result: DetectionResult, n_bootstrap: int = N_BOOTSTRAP) -> dict:
    months = join_labels(simulation, result.detections)
    customers = result.test_customers
    draws = bootstrap_draws(len(customers), n_bootstrap, simulation.config.seed)

    samples = {
        setup: metrics_from_totals(customer_counts(months, customers, setup)[draws].sum(axis=1))
        for setup in SETUPS
    }
    setups = {}
    for setup in SETUPS:
        found = confusion(months, setup)
        setups[setup] = {
            "confusion": asdict(found),
            **{metric: _estimate(getattr(found, metric), samples[setup][metric]) for metric in METRICS},
            "recall_by_fault": {
                fault: _recall_for([m for m in months if m.anomaly_type in (fault, NO_ANOMALY)], customers, setup, draws)
                for fault in (LEAK, BYPASS)
            },
            "detection_delay": detection_delay(months, setup),
            "blind_spots": blind_spots(months, setup),
        }
    differences = {}
    for name, (first, second) in COMPARISONS.items():
        differences[name] = {
            metric: _estimate(
                setups[first][metric]["value"] - setups[second][metric]["value"],
                samples[first][metric] - samples[second][metric],
            )
            for metric in METRICS
        }
    return {
        "test_customers": len(customers),
        "test_months": len(months),
        "fault_months": sum(m.is_fault for m in months),
        "setups": setups,
        "differences": differences,
    }


def _summary(values: Sequence[float]) -> Dict[str, float]:
    return {"mean": round(mean(values), 4), "min": round(min(values), 4), "max": round(max(values), 4)}


def seed_study(config: SimulationConfig, n_seeds: int = N_SEEDS, on_seed: Optional[Callable[[int], None]] = None) -> dict:
    """Repeat the whole simulation on the next n_seeds seeds, leaving out the headline seed."""
    found: Dict[str, List[Confusion]] = {setup: [] for setup in SETUPS}
    seeds = [config.seed + offset for offset in range(1, n_seeds + 1)]
    for seed in seeds:
        simulation = run_simulation(replace(config, seed=seed))
        months = join_labels(simulation, run_detection(simulation).detections)
        for setup in SETUPS:
            found[setup].append(confusion(months, setup))
        if on_seed:
            on_seed(seed)
    return {
        "seeds": seeds,
        "setups": {
            setup: {metric: _summary([getattr(c, metric) for c in runs]) for metric in METRICS}
            for setup, runs in found.items()
        },
    }


def subtle_fault_run(config: SimulationConfig, n_bootstrap: int = N_BOOTSTRAP) -> dict:
    """The same customers with faults much closer to normal use."""
    simulation = run_simulation(replace(config, faults=SUBTLE_FAULTS))
    report = evaluate_run(simulation, run_detection(simulation), n_bootstrap)
    return {"faults": asdict(SUBTLE_FAULTS), **report}


def build_report(
    simulation: Simulation,
    result: DetectionResult,
    n_bootstrap: int = N_BOOTSTRAP,
    n_seeds: int = N_SEEDS,
    on_seed: Optional[Callable[[int], None]] = None,
) -> dict:
    return {
        "notice": NOTICE,
        "assumptions": asdict(simulation.config),
        "bootstrap": {"resamples": n_bootstrap, "unit": "customer", "interval": "95% percentile"},
        "forest_note": "contamination 0.05 equals the injected fault share",
        **evaluate_run(simulation, result, n_bootstrap),
        "seed_study": seed_study(simulation.config, n_seeds, on_seed),
        "subtle_faults": subtle_fault_run(simulation.config, n_bootstrap),
    }


def write_metrics(report: Mapping, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "metrics.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def write_confusion_plot(report: Mapping, output_dir: Path) -> Path:
    """One panel per setup. Shade is the share of the actual row, so a rare class stays readable."""
    import matplotlib  # only this figure needs it: the app's requirements do not include it

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ink, muted = "#16202E", "#5B6778"
    shades = matplotlib.colors.LinearSegmentedColormap.from_list("navy", ["#EDF2F9", "#12335E"])
    figure, axes = plt.subplots(1, len(SETUPS), figsize=(11, 4.6), dpi=200, sharey=True)
    for axis, setup in zip(axes, SETUPS):
        data = report["setups"][setup]
        c = data["confusion"]
        counts = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]], dtype=float)
        rows = counts.sum(axis=1, keepdims=True)
        shares = _ratio(counts, np.broadcast_to(rows, counts.shape))
        axis.imshow(shares, cmap=shades, vmin=0, vmax=1)
        for row in range(2):
            for column in range(2):
                colour = "white" if shares[row, column] > 0.7 else ink
                axis.text(column, row - 0.08, f"{int(counts[row, column]):,}", ha="center", va="center",
                          fontsize=17, fontweight="bold", color=colour)
                axis.text(column, row + 0.2, f"{shares[row, column]:.1%} of row", ha="center", va="center",
                          fontsize=9, color=colour)
        axis.set_xticks([0, 1], ["Not flagged", "Flagged"], color=ink)
        axis.set_yticks([0, 1], ["Normal", "Fault"], color=ink)
        axis.set_xlabel("What the setup said", color=muted)
        axis.tick_params(length=0)
        for side in axis.spines.values():
            side.set_visible(False)
        axis.set_xticks([0.5], minor=True)
        axis.set_yticks([0.5], minor=True)
        axis.grid(which="minor", color="white", linewidth=3)
        axis.tick_params(which="minor", length=0)
        axis.set_title(
            f"{SETUP_TITLES[setup]}\nPrecision {data['precision']['value']:.2f}   "
            f"Recall {data['recall']['value']:.2f}   F1 {data['f1']['value']:.2f}",
            fontsize=11, color=ink, loc="left",
        )
    axes[0].set_ylabel("What actually happened", color=muted)
    figure.text(0.01, 0.01, f"{NOTICE} {report['test_months']:,} test months from "
                f"{report['test_customers']} held-out customers; seed {report['assumptions']['seed']}.",
                fontsize=8.5, color=muted)
    figure.tight_layout(rect=(0, 0.05, 1, 0.96))
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "confusion_matrices.png"
    figure.savefig(path, facecolor="white")
    plt.close(figure)
    return path
