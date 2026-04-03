"""Utilities to run the `sp_perf` runner and extract a performance score.

This module Provide PerformanceScoreDriver that computes a performance score by averaging the three
columns: `gpuLoad`, `hw-cpu-cycles`, and `hw-instructions` from the
produced `sp_*.csv` file.
"""

WORK_DIR = "."
DATA_DIR = "data"
COLUMNS = ["gpuCycle"]

import platform
import csv
import glob
import os
import statistics
import time
import subprocess
from typing import Optional, List

def _parse_csv_column_values(filepath: str, target_columns: Optional[List[str]] = None) -> dict:
    """Return a mapping column -> list of numeric values from the CSV.

    Values are taken directly from each row for the named columns.
    """
    cols: dict[str, list[float]] = {c: [] for c in target_columns}
    with open(filepath, newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        missing = [c for c in target_columns if c not in headers]
        if missing:
            print(f"missing expected columns in CSV: {missing}")
            return None

        for row in reader:
            for c in target_columns:
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

def find_last_greater_than_50(lst):
    # 从后往前遍历
    for i in range(len(lst)-1, 4, -1):
        if lst[i] > 500000 and lst[i-1] != 0 and lst[i-2] != 0 and lst[i-3] != 0:
            return i  # 返回索引位置
    return -1

def _column_means_from_csv(filepath: str, target_columns: Optional[List[str]] = COLUMNS) -> dict:
    """Return a mapping column -> mean across rows for the CSV file."""
    cols = _parse_csv_column_values(filepath, target_columns)
    if cols is None:
        return None
    means: dict[str, float] = {}
    for c, values in cols.items():
        if not values:
            raise ValueError(f"no numeric values found for column '{c}' in {filepath}")
        pos = find_last_greater_than_50(values)
        # means[c] = float(statistics.mean(values))
        if pos == -1:
            means[c] = float(statistics.mean(values))
        else:
            means[c] = float(statistics.mean(values[:pos+1]))
    return means

def runcmd_block(cmd, cwd=None):
    if cwd:
        return subprocess.run(cmd, shell = True, capture_output = True, text = True, cwd = cwd)
    return subprocess.run(cmd, shell = True, capture_output = True, text = True)

def wait_for_boot_complete():
    max_time = 120  # 最多 2 分钟
    t = 0
    while t < max_time:
        result = runcmd_block(r"hdc list targets")
        if result.stdout.strip() != '[Empty]':
            print("设备重启已完成")
            time.sleep(20)
            return result.stdout.strip()
        time.sleep(10)
        t += 10
    return None

def prevent_reboot():
    INIT_BAT = f"setup\init-uifirsttest-PLR.bat"
    ans = wait_for_boot_complete()
    runcmd_block(INIT_BAT)
    ans = wait_for_boot_complete()
    return ans

def _run_script_and_get_column_means() -> dict:
    """Optionally run `sp_script` and return per-column means for the latest CSV."""
    start_time = 0
    while start_time < 2:   # 最多尝试两次
        if platform.system() == "Windows":
            proc = subprocess.run([
                'powershell', 
                '-ExecutionPolicy', 'Bypass', 
                '-File', '.\\sp_perf.ps1'
            ], cwd=WORK_DIR, capture_output=True, text=True)
        else:
            proc = subprocess.run([
                './sp_perf.sh'
            ], cwd=WORK_DIR, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"script failed (rc={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")

        pattern = os.path.join(DATA_DIR, "sp_*.csv")
        matches = glob.glob(pattern)
        start_time += 1
        if not matches and start_time == 1:
            # 第一次尝试, 还有机会: 等待机器重启完成, 然后调用锁频脚本重启, 再次进入 Cycles 采集
            prevent_reboot()
            continue
        latest = max(matches, key=os.path.getmtime)
        cols = _column_means_from_csv(latest)
        if cols is None and start_time == 1:
            print("重启: missing expected columns in CSV")
            prevent_reboot()
            continue
        if cols is not None:
            return cols, latest
    raise FileNotFoundError(f"no files matching {pattern}")

class PerformanceScoreDriver:
    """Driver that holds a baseline distribution and computes loss values.

    The driver builds a baseline distribution by calling
    `get_performance_score` `sample_size` times (running the script each
    time when `run_script=True`). It stores the baseline mean and std.
    """

    def __init__(
        self,
        init_sample_size: int,      # 仅用于检测 gpuCycles 是否准确
        verbose: bool = False,
    ) -> None:
        self.verbose = verbose

        # Build per-column sample lists by running the script `sample_size` times
        samples_per_column: dict[str, List[float]] = {}
        for i in range(int(init_sample_size)):
            if self.verbose:
                print(f"baseline sample {i+1}/{init_sample_size}")
            col_means, _ = _run_script_and_get_column_means()
            for c, m in col_means.items():
                if c not in samples_per_column:
                    samples_per_column[c] = []
                samples_per_column[c].append(float(m))

        # if not samples_per_column:
        #     raise ValueError("no baseline samples collected")

        # compute per-column mean and std
        self.samples_per_column = samples_per_column
        self.base_mean_per_column: dict[str, float] = {}
        self.base_last_per_column: dict[str, float] = {}
        for c, vals in samples_per_column.items():
            self.base_mean_per_column[c] = float(statistics.mean(vals))
            self.base_last_per_column[c] = float(vals[-1])
            print(vals)

        if self.verbose:
            print(f"baseline means={self.base_mean_per_column} last={self.base_last_per_column}")

    def loss(
        self,
    ) -> float:
        sample_col_means, sample_name = _run_script_and_get_column_means()

        # compute per-column z-scores; baseline stats stored per-column
        z_scores: List[float] = []
        for c, sample_val in sample_col_means.items():
            # if c not in COLUMNS:
            #     continue
            z = float(sample_val)
            tag = f'column={c} sample={sample_val}'

            if self.samples_per_column:
                if c not in self.base_mean_per_column:
                    raise ValueError(f"unknown baseline column '{c}'")
                base_mean = self.base_mean_per_column[c]
                base_last = self.base_last_per_column[c]
                # 如果 base_std 过大, 则结果不可信
                tag += f' base_mean={base_mean} '
            if self.verbose:
                print(tag)
            z_scores.append(z)

        # Average per-column z-scores. Lower z is better.
        return float(statistics.mean(z_scores)) * 1e-5, sample_name

if __name__ == "__main__":
    # 这里的关键也是在 sp_perf 脚本, 如果 5 次差别大则不可信;
    # 实际动效场景, 后续可以换成解析 trace 找动效段
    # for i in range(1):
    #     driver = PerformanceScoreDriver(init_sample_size=5, verbose=True)
    #     print(f'loss={driver.loss()}')

    # 测试 data.csv 求平均的逻辑: 在动效结束时求平均, 而不是采样结束时求.
    data_dir = "data"
    test_path = f"data/bgKBS_X_0_0/sp_112358.csv"
    print("total mean = ", _column_means_from_csv(test_path))
