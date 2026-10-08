"""Measure how many realistic CRNN errors and leaks Stage 3 catches, and its false-alarm rate.

For every reading that has enough history, the true reading is scored untouched (false-alarm check)
and again with one injected error: last digit wrong, one dropped digit, one extra digit, one wrong
digit elsewhere, and a 3-10x leak spike. "Caught" means is_anomaly or needs_retake.

    python scripts/evaluate_anomaly_model.py                          # real readings from DATABASE_URL
    python scripts/evaluate_anomaly_model.py --csv histories.csv
    python scripts/evaluate_anomaly_model.py --train-split 0.7        # train on 70% of households, test on the rest
    python scripts/evaluate_anomaly_model.py --demo --train-split 0.7 # DEMO data, pipeline testing only
"""
import argparse
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median
from typing import Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data import DEMO_BANNER, contains_demo, load_histories_csv, load_histories_db  # noqa: E402

from anomaly.config import AnomalyConfig  # noqa: E402
from anomaly.demo_data import generate_demo_histories  # noqa: E402
from anomaly.features import ReadingPoint, build_periods  # noqa: E402
from anomaly.model import AnomalyModel, build_training_matrix  # noqa: E402
from anomaly.readings import digits_to_m3, m3_to_digits  # noqa: E402
from anomaly.service import assess  # noqa: E402


def _other_digit(d: str, rng: random.Random) -> str:
    return rng.choice([c for c in "0123456789" if c != d])


def last_digit_wrong(s: str, rng: random.Random) -> str:
    return s[:-1] + _other_digit(s[-1], rng)


def dropped_digit(s: str, rng: random.Random) -> str:
    i = rng.randrange(len(s))
    return s[:i] + s[i + 1:]


def extra_digit(s: str, rng: random.Random) -> str:
    i = rng.randrange(len(s) + 1)
    return s[:i] + rng.choice("0123456789") + s[i:]


def wrong_digit_elsewhere(s: str, rng: random.Random) -> str:
    i = rng.randrange(len(s) - 1)
    return s[:i] + _other_digit(s[i], rng) + s[i + 1:]


DIGIT_ERRORS: Dict[str, Callable[[str, random.Random], str]] = {
    "last_digit_wrong": last_digit_wrong,
    "dropped_digit": dropped_digit,
    "extra_digit": extra_digit,
    "wrong_digit_other_position": wrong_digit_elsewhere,
}


@dataclass
class Tally:
    cases: int = 0
    caught: int = 0
    labels: Counter = field(default_factory=Counter)
    missed_abs_error_m3: List[float] = field(default_factory=list)

    def add(self, caught: bool, label: str, abs_error: Optional[float] = None) -> None:
        self.cases += 1
        self.caught += caught
        if caught:
            self.labels[label] += 1
        elif abs_error is not None:
            self.missed_abs_error_m3.append(abs_error)

    @property
    def rate(self) -> float:
        return self.caught / self.cases if self.cases else float("nan")


def evaluate(histories, model, config: AnomalyConfig, seed: int) -> Dict[str, Tally]:
    rng = random.Random(seed)
    tallies: Dict[str, Tally] = defaultdict(Tally)

    for hid, points in histories.items():
        points = sorted(points, key=lambda p: p.date)
        for j in range(config.min_history_periods + 1, len(points)):
            history, truth = points[:j], points[j]

            def run(reading_m3: float):
                return assess(hid, history, reading_m3, truth.date, model, config)

            clean = run(truth.reading_m3)
            tallies["untouched (false alarms)"].add(clean.is_anomaly, clean.anomaly_type)

            true_digits = m3_to_digits(truth.reading_m3, config)
            for name, inject in DIGIT_ERRORS.items():
                bad = inject(true_digits, rng)
                conv = digits_to_m3(bad, config)
                if not conv.ok:
                    tallies[name].add(True, "RETAKE_WRONG_LENGTH")
                    continue
                r = run(conv.reading_m3)
                tallies[name].add(r.is_anomaly, r.anomaly_type, abs(conv.reading_m3 - truth.reading_m3))

            normal_daily = median(p.daily_consumption for p in build_periods(history))
            days = max(1.0, (truth.date - history[-1].date).total_seconds() / 86400)
            leak_m3 = history[-1].reading_m3 + max(normal_daily, 0.05) * rng.uniform(3, 10) * days
            r = run(leak_m3)
            tallies["leak_spike_3x_10x"].add(r.is_anomaly, r.anomaly_type, abs(leak_m3 - truth.reading_m3))
    return tallies


def print_report(tallies: Dict[str, Tally], label: str) -> None:
    print(f"\n{label}")
    print(f"{'error type':<30}{'cases':>7}{'caught':>8}{'rate':>8}  {'missed: mean |err| m3':>22}  labels when caught")
    print("-" * 110)
    order = list(DIGIT_ERRORS) + ["leak_spike_3x_10x", "untouched (false alarms)"]
    for name in order:
        t = tallies.get(name)
        if not t:
            continue
        missed = f"{mean(t.missed_abs_error_m3):.3f}" if t.missed_abs_error_m3 else "-"
        labels = ", ".join(f"{k}:{v}" for k, v in t.labels.most_common(3)) or "-"
        print(f"{name:<30}{t.cases:>7}{t.caught:>8}{t.rate:>8.1%}  {missed:>22}  {labels}")
    print("\nFor 'untouched', the rate is the FALSE ALARM rate (lower is better).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--csv", type=Path)
    source.add_argument("--demo", action="store_true", help="Evaluate on generated DEMO households")
    parser.add_argument("--train-split", type=float, help="Train a fresh model on this share of households, test on the rest")
    parser.add_argument("--model", type=Path, help="Saved model to evaluate (default: ANOMALY_MODEL_PATH)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    config = AnomalyConfig.from_env()
    if args.demo:
        histories = generate_demo_histories()
    elif args.csv:
        histories = load_histories_csv(args.csv)
    else:
        histories = load_histories_db()

    if contains_demo(histories) and not args.demo:
        sys.exit("Refusing to evaluate: the data contains DEMO- households. Real evaluation must use real data only.")
    if args.demo:
        print(DEMO_BANNER)
    if not histories:
        sys.exit("No reading histories found.")

    ids = sorted(histories)
    model: Optional[AnomalyModel] = None
    if args.train_split:
        random.Random(args.seed).shuffle(ids)
        cut = max(1, int(len(ids) * args.train_split))
        train_ids, test_ids = ids[:cut], ids[cut:]
        if not test_ids:
            sys.exit("--train-split leaves no test households.")
        model = AnomalyModel.train(build_training_matrix([histories[i] for i in train_ids], config), config)
        histories = {i: histories[i] for i in test_ids}
        setup = f"held-out: trained on {len(train_ids)} households, tested on {len(test_ids)}"
    else:
        path = args.model or config.model_path
        if Path(path).exists():
            model = AnomalyModel.load(path)
            setup = f"saved model {path} (in-sample if it was trained on these households; prefer --train-split)"
        else:
            setup = "RULES ONLY: no trained model found"

    title = f"Stage 3 evaluation ({setup})"
    if args.demo:
        title = "DEMO DATA, NOT A REAL RESULT. " + title
    print_report(evaluate(histories, model, config, args.seed), title)


if __name__ == "__main__":
    main()
