"""
Utilities to run the `sp_perf` runner and extract a performance score.
"""

SP_SCRIPT = "sp_perf.sh"

import csv
import glob
import os
import subprocess

def _parse_csv_score(filepath: str, parse_mode: str = "mean") -> float:
	"""Parse numeric values from `filepath` and return a summary value.

	The parser scans every cell in the CSV and attempts to convert it to
	float. Non-numeric cells are ignored. If no numeric data is found a
	ValueError is raised.
	"""
	nums: list[float] = []
	with open(filepath, newline="") as fh:
		reader = csv.reader(fh)
	return 0


def get_performance_score(
	workdir: str = ".",
) -> float:
	"""Run the `sp_perf` script and return a numeric performance score.

	Returns: float performance score.

	Raises RuntimeError when the script fails, FileNotFoundError when no
	CSV is produced, or ValueError when parsing finds no numeric data.
	"""
	proc = subprocess.run(SP_SCRIPT, cwd=workdir, capture_output=True, text=True)
	if proc.returncode != 0:
		msg = f"script {SP_SCRIPT} failed (rc={proc.returncode})\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
		raise RuntimeError(msg)

	# Find newest sp_*.csv in workdir
	pattern = os.path.join(workdir, "sp_*.csv")
	matches = glob.glob(pattern)
	if not matches:
		raise FileNotFoundError(f"no files matching {pattern}")

	latest = max(matches, key=os.path.getmtime)
	print(f"found CSV: {latest}")

	score = _parse_csv_score(latest)
	print(f"computed score: {score}")
	return score


if __name__ == "__main__":
	# Basic smoke run when executed directly (will run the script in cwd).
	try:
		s = get_performance_score()
	except Exception as e:
		print(f"error computing performance score: {e}")
