"""Train the Stage 3 IsolationForest on every household's reading history.

    python scripts/train_anomaly_model.py                       # real readings from DATABASE_URL
    python scripts/train_anomaly_model.py --csv histories.csv   # household_id,reading_date,reading_m3
    python scripts/train_anomaly_model.py --demo                # DEMO data, pipeline testing only

DEMO- households and the three app seed meters are excluded from DB training unless --demo is given.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _data import DEMO_BANNER, contains_demo, load_histories_csv, load_histories_db  # noqa: E402

from anomaly.config import AnomalyConfig  # noqa: E402
from anomaly.demo_data import generate_demo_histories  # noqa: E402
from anomaly.model import AnomalyModel, build_training_matrix  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--csv", type=Path, help="Reading histories CSV instead of the database")
    source.add_argument("--demo", action="store_true", help="Train on freshly generated DEMO households")
    parser.add_argument("--output", type=Path, help="Where to save the model (default: ANOMALY_MODEL_PATH)")
    args = parser.parse_args()

    config = AnomalyConfig.from_env()
    if args.demo:
        histories = generate_demo_histories()
    elif args.csv:
        histories = load_histories_csv(args.csv)
    else:
        histories = load_histories_db()

    is_demo = args.demo or contains_demo(histories)
    if is_demo:
        print(DEMO_BANNER)

    X = build_training_matrix(histories.values(), config)
    print(f"Households: {len(histories)}   training periods: {len(X)}   features: {X.shape[1]}")
    if len(X) < 10:
        sys.exit(
            "Not enough history to train (need >= 10 periods with at least "
            f"{config.min_history_periods} prior periods each). Use --demo to test the pipeline."
        )

    model = AnomalyModel.train(X, config)
    path = model.save(args.output or config.model_path)
    flagged = int((model.estimator.predict(X) == -1).sum())
    print(f"Saved model to {path}")
    print(f"contamination={config.contamination}  flagged {flagged}/{len(X)} training periods")
    if is_demo:
        print("This model was trained on DEMO data. Retrain on real WASAC readings before using it.")


if __name__ == "__main__":
    main()
