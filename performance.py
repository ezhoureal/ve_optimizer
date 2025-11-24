"""Utilities to run the `sp_perf` runner and extract a performance score.

This module computes a simple performance score by averaging the three
columns: `gpuLoad`, `hw-cpu-cycles`, and `hw-instructions` from the
produced `sp_*.csv` file.
"""

WORK_DIR = "."
SP_SCRIPT = "./sp_perf.sh"
COLUMNS = ["gpuLoad", "hw-cpu-cycles", "hw-instructions"]

import csv
import glob
import os
import statistics
import subprocess
from typing import Optional, List

def _parse_csv_column_values(filepath: str, target_columns: Optional[List[str]] = None) -> dict:
    """Return a mapping column -> list of numeric values from the CSV.

    Values are taken directly from each row for the named columns.
    """

    cols: dict[str, list[float]] = {c: [] for c in COLUMNS}
    with open(filepath, newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [c for c in COLUMNS if c not in headers]
        if missing:
            raise ValueError(f"missing expected columns in CSV: {missing}")

        for row in reader:
            for c in COLUMNS:
                raw = row.get(c)
                if raw is None:
                    continue
                s = raw.strip()
                if not s:
                    continue
                try:
                    cols[c].append(float(s))
                except ValueError:
                    try:
                        cols[c].append(float(s.replace(",", "")))
                    except ValueError:
                        continue

    return cols


def _column_means_from_csv(filepath: str, target_columns: Optional[List[str]] = None) -> dict:
    """Return a mapping column -> mean across rows for the CSV file."""
    cols = _parse_csv_column_values(filepath, target_columns)
    means: dict[str, float] = {}
    for c, values in cols.items():
        if not values:
            raise ValueError(f"no numeric values found for column '{c}' in {filepath}")
        means[c] = float(statistics.mean(values))
    return means


def _run_script_and_get_column_means() -> dict:
    """Optionally run `sp_script` and return per-column means for the latest CSV."""
    proc = subprocess.run(["bash", SP_SCRIPT], cwd=WORK_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"script {SP_SCRIPT} failed (rc={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")

    pattern = os.path.join(WORK_DIR, "sp_*.csv")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"no files matching {pattern}")

    latest = max(matches, key=os.path.getmtime)
    return _column_means_from_csv(latest)

class PerformanceScoreDriver:
    """Driver that holds a baseline distribution and computes loss values.

    The driver builds a baseline distribution by calling
    `get_performance_score` `sample_size` times (running the script each
    time when `run_script=True`). It stores the baseline mean and std.
    """

    def __init__(
        self,
        sample_size: int = 50,
        verbose: bool = False,
        min_std: float = 1e-6,
    ) -> None:
        self.verbose = verbose

        # Build per-column sample lists by running the script `sample_size` times
        samples_per_column: dict[str, List[float]] = {}
        for i in range(int(sample_size)):
            if self.verbose:
                print(f"baseline sample {i+1}/{sample_size}")
            col_means = _run_script_and_get_column_means()
            for c, m in col_means.items():
                if c not in samples_per_column:
                    samples_per_column[c] = []
                samples_per_column[c].append(float(m))

        if not samples_per_column:
            raise ValueError("no baseline samples collected")

        # compute per-column mean and std
        self.samples_per_column = samples_per_column
        self.base_mean_per_column: dict[str, float] = {}
        self.base_std_per_column: dict[str, float] = {}
        for c, vals in samples_per_column.items():
            self.base_mean_per_column[c] = float(statistics.mean(vals))
            if len(vals) >= 2:
                self.base_std_per_column[c] = float(statistics.stdev(vals))
            else:
                self.base_std_per_column[c] = float(min_std)
            if self.base_std_per_column[c] < min_std:
                self.base_std_per_column[c] = float(min_std)

        if self.verbose:
            print(f"baseline means={self.base_mean_per_column}")
            print(f"baseline stds={self.base_std_per_column}")

    def loss(
        self
    ) -> float:
        sample_col_means = _run_script_and_get_column_means()

        # compute per-column z-scores; baseline stats stored per-column
        z_scores: List[float] = []
        for c, sample_val in sample_col_means.items():
            if c not in self.base_mean_per_column:
                raise ValueError(f"unknown baseline column '{c}'")
            base_mean = self.base_mean_per_column[c]
            base_std = self.base_std_per_column[c]
            z = (float(sample_val) - base_mean) / base_std
            if self.verbose:
                print(f'column={c} sample={sample_val} base_mean={base_mean} base_std={base_std} z={z}')
            z_scores.append(z)

        # Average per-column z-scores. Lower z is better.
        return float(statistics.mean(z_scores))


if __name__ == "__main__":
    driver = PerformanceScoreDriver(sample_size=5, verbose=True)
    print(f'loss={driver.loss()}')