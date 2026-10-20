#!/usr/bin/env python3
"""
Benchmark harness for algorithms that identify shared transit stops.

An algorithm takes raw GTFS Schedule stops and groups the ones that are really
the same physical stop under one ``unique_id``. This script does not run an
algorithm. It scores the *output* of one against a set of test cases, so
different algorithms (or different parameters of one algorithm) can be compared
on equal terms.

Standard library only; Python 3.8+.

Inputs
------
1. Deduplicated stops CSV (``--dedup``)
   Required columns: ``unique_id``, ``latitude``, ``longitude``.
2. GTFS stops CSV (``--gtfs``)
   Required columns: ``GTFS Schedule Name``, ``GTFS Schedule Stop ID``,
   ``unique_id``, ``latitude``, ``longitude``. ``unique_id`` is the id of the
   deduplicated stop the GTFS stop was assigned to by the algorithm.
   Extra columns in either file are ignored.

Usage
-----
    python shared_stop_benchmark.py --dedup dedup.csv --gtfs gtfs_stops.csv
    python shared_stop_benchmark.py --dedup dedup.csv --gtfs gtfs_stops.csv \\
        --label "geohash-7" --json results/geohash-7.json

Exit status is 0 when nothing failed and 1 otherwise (skipped tests are not
failures unless ``--fail-on-skipped`` is given).

Test cases
----------
* File format checks for both inputs (one test per rule).
* "Should match" fixtures: GTFS stops that must share a ``unique_id``.
  Includes the "Caltrans District Focus Stops" category (one per district).
* "Should not match" fixtures: GTFS stops that must NOT share a ``unique_id``.

To add a fixture, append a ``same(...)`` call to ``SHOULD_MATCH_FIXTURES`` or a
``different(...)`` call to ``SHOULD_NOT_MATCH_FIXTURES`` below. Every category
used in a fixture gets its own line in the report, so categories are the
quality dimensions you compare algorithms on; invent new ones freely.

A fixture whose stops are not present in the supplied GTFS file is reported as
*skipped* rather than passed or failed, so a run against a partial dataset is
not silently graded on stops that were never there.
"""

import argparse
import csv
import json
import math
import re
import sys
import unittest
from collections import OrderedDict
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------- #
# Fixtures - edit this section to add test cases
# --------------------------------------------------------------------------- #

# A GTFS stop is identified by (GTFS Schedule Name, GTFS Schedule Stop ID).
StopRef = Tuple[str, str]


@dataclass
class Fixture:
    name: str
    category: str
    stops: List[StopRef]
    notes: str = ""


def same(name: str, category: str, *stops: StopRef, notes: str = "") -> Fixture:
    """Fixture: all of `stops` must be assigned the same unique_id."""
    return Fixture(name, category, list(stops), notes)


def different(name: str, category: str, *stops: StopRef, notes: str = "") -> Fixture:
    """Fixture: every one of `stops` must be assigned a different unique_id."""
    return Fixture(name, category, list(stops), notes)


CALTRANS_CATEGORY = "Caltrans District Focus Stops"

# One entry per Caltrans district. Replace the empty stop list with two or more
# (GTFS Schedule Name, GTFS Schedule Stop ID) pairs that are physically the same
# stop and that sit in that district. Until populated, the case is reported as
# skipped.
CALTRANS_DISTRICT_FIXTURES: List[Fixture] = [
    same("District 1 - Eureka (North Coast)", CALTRANS_CATEGORY),
    same("District 2 - Redding (Northeastern CA)", CALTRANS_CATEGORY),
    same("District 3 - Marysville (Sacramento Area)", CALTRANS_CATEGORY),
    same("District 4 - Oakland (Bay Area)", CALTRANS_CATEGORY),
    same("District 5 - San Luis Obispo (Central Coast)", CALTRANS_CATEGORY),
    same("District 6 - Fresno (Central Valley)", CALTRANS_CATEGORY),
    same("District 7 - Los Angeles", CALTRANS_CATEGORY),
    same("District 8 - San Bernardino (Inland Empire)", CALTRANS_CATEGORY),
    same("District 9 - Bishop (Eastern Sierra)", CALTRANS_CATEGORY),
    same("District 10 - Stockton (Central Sierra / San Joaquin)", CALTRANS_CATEGORY),
    same("District 11 - San Diego", CALTRANS_CATEGORY),
    same("District 12 - Irvine (Orange County)", CALTRANS_CATEGORY),
]

# Stops that must share a unique_id. Template:
#   same("Short description", "Category name",
#        ("Agency A Schedule", "stop_123"),
#        ("Agency B Schedule", "9876"),
#        notes="why these are the same stop")
SHOULD_MATCH_FIXTURES: List[Fixture] = [
    # same("Transfer hub shared by two agencies", "Same stop, different agencies",
    #      ("Agency A Schedule", "stop_123"), ("Agency B Schedule", "9876")),
    # same("Duplicate stop record within one feed", "Same stop, same agency",
    #      ("Agency A Schedule", "stop_123"), ("Agency A Schedule", "stop_123_dup")),
    *CALTRANS_DISTRICT_FIXTURES,
]

# Stops that must NOT share a unique_id. Template:
#   different("Short description", "Category name",
#             ("Agency A Schedule", "stop_123"),
#             ("Agency A Schedule", "stop_124"),
#             notes="why these are different stops")
SHOULD_NOT_MATCH_FIXTURES: List[Fixture] = [
    # different("Opposite sides of a street", "Opposite sides of street",
    #           ("Agency A Schedule", "stop_123_north"), ("Agency A Schedule", "stop_123_south")),
    # different("Adjacent stops on one route", "Nearby but distinct stops",
    #           ("Agency A Schedule", "stop_200"), ("Agency A Schedule", "stop_201")),
]

# --------------------------------------------------------------------------- #
# Input schemas and file loading
# --------------------------------------------------------------------------- #

DEDUP_LABEL = "Deduplicated stops"
GTFS_LABEL = "GTFS stops"

DEDUP_COLUMNS = ["unique_id", "latitude", "longitude"]
GTFS_COLUMNS = [
    "GTFS Schedule Name",
    "GTFS Schedule Stop ID",
    "unique_id",
    "latitude",
    "longitude",
]
GTFS_NAME, GTFS_STOP_ID, GTFS_UID, GTFS_LAT, GTFS_LON = GTFS_COLUMNS

MAX_ROW_ERRORS_SHOWN = 5
_DECIMAL_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)$")


@dataclass
class FileData:
    path: str
    header: List[str] = field(default_factory=list)
    rows: List[Dict[str, Optional[str]]] = field(default_factory=list)
    load_error: Optional[str] = None


def load_csv(path: str) -> FileData:
    data = FileData(path)
    try:
        # utf-8-sig so a BOM from Excel doesn't corrupt the first header name.
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            data.header = [h.strip() for h in (reader.fieldnames or [])]
            reader.fieldnames = data.header
            data.rows = list(reader)
    except FileNotFoundError:
        data.load_error = f"file not found: {path}"
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        data.load_error = f"could not read as CSV: {exc}"
    return data


def is_blank(value: Optional[str]) -> bool:
    return value is None or value.strip() == ""


def coordinate_error(value: Optional[str], low: float, high: float) -> Optional[str]:
    """Return a problem description, or None if value is a decimal in [low, high]."""
    if is_blank(value):
        return "blank"
    text = value.strip()
    if not _DECIMAL_RE.match(text):
        return f"not a decimal number: {text!r}"
    number = float(text)
    if not low <= number <= high:
        return f"out of range [{low:g}, {high:g}]: {text}"
    return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


class Inputs:
    """Both input files plus a lookup from GTFS stop -> assigned unique_ids."""

    def __init__(self, dedup: FileData, gtfs: FileData):
        self.dedup = dedup
        self.gtfs = gtfs
        self.ids: Dict[StopRef, Set[str]] = {}
        self.coords: Dict[StopRef, Tuple[float, float]] = {}
        if self.gtfs_usable:
            for row in gtfs.rows:
                if any(is_blank(row.get(c)) for c in (GTFS_NAME, GTFS_STOP_ID, GTFS_UID)):
                    continue
                ref = (row[GTFS_NAME].strip(), row[GTFS_STOP_ID].strip())
                self.ids.setdefault(ref, set()).add(row[GTFS_UID].strip())
                if not coordinate_error(row.get(GTFS_LAT), -90, 90) and not coordinate_error(
                    row.get(GTFS_LON), -180, 180
                ):
                    self.coords[ref] = (float(row[GTFS_LAT]), float(row[GTFS_LON]))

    @property
    def gtfs_usable(self) -> bool:
        return self.gtfs.load_error is None and all(c in self.gtfs.header for c in GTFS_COLUMNS)

    def spread_m(self, refs: List[StopRef]) -> Optional[float]:
        """Largest distance between any two of refs, if coordinates are known."""
        points = [self.coords[r] for r in refs if r in self.coords]
        if len(points) < 2:
            return None
        return max(haversine_m(*a, *b) for a, b in combinations(points, 2))


# --------------------------------------------------------------------------- #
# Test framework: unittest cases carrying a category, collected by a custom result
# --------------------------------------------------------------------------- #

class BenchmarkTest(unittest.TestCase):
    """A single named, categorised check. `check(test)` fails/skips via self."""

    def __init__(self, category: str, name: str, check):
        super().__init__("runTest")
        self.category = category
        self.name = name
        self._check = check

    def runTest(self):
        self._check(self)

    def id(self):
        return f"{self.category} :: {self.name}"

    def shortDescription(self):
        return self.name


@dataclass
class Outcome:
    category: str
    name: str
    status: str  # "passed" | "failed" | "skipped"
    message: str = ""


class BenchmarkResult(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.outcomes: List[Outcome] = []

    def _record(self, test, status, message=""):
        self.outcomes.append(Outcome(test.category, test.name, status, message))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed", str(err[1]))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "failed", f"unexpected error: {err[0].__name__}: {err[1]}")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)


def _fmt_row_errors(errors: List[str], total: int) -> str:
    shown = "; ".join(errors[:MAX_ROW_ERRORS_SHOWN])
    more = f" (+{total - MAX_ROW_ERRORS_SHOWN} more)" if total > MAX_ROW_ERRORS_SHOWN else ""
    return f"{total} bad row(s): {shown}{more}"


# ---- file format tests ----------------------------------------------------- #

def _readable_check(data: FileData):
    def check(t: unittest.TestCase):
        if data.load_error:
            t.fail(data.load_error)
        if not data.header:
            t.fail("file is empty (no header row)")
        if not data.rows:
            t.fail("file has a header but no data rows")
    return check


def _header_check(data: FileData, required: List[str]):
    def check(t: unittest.TestCase):
        if data.load_error:
            t.skipTest("file could not be read")
        missing = [c for c in required if c not in data.header]
        if missing:
            t.fail(f"missing column(s): {', '.join(missing)}; found: {', '.join(data.header)}")
    return check


def _column_check(data: FileData, column: str, validate):
    """Apply validate(value) -> error|None to every row of `column`."""
    def check(t: unittest.TestCase):
        if data.load_error or column not in data.header:
            t.skipTest(f"column {column!r} unavailable (see header test)")
        errors = []
        for line, row in enumerate(data.rows, start=2):  # line 1 is the header
            problem = validate(row.get(column))
            if problem:
                errors.append(f"line {line}: {problem}")
        if errors:
            t.fail(_fmt_row_errors(errors, len(errors)))
    return check


def _not_blank(value: Optional[str]) -> Optional[str]:
    return "blank" if is_blank(value) else None


def _lat(value: Optional[str]) -> Optional[str]:
    return coordinate_error(value, -90, 90)


def _lon(value: Optional[str]) -> Optional[str]:
    return coordinate_error(value, -180, 180)


def format_tests(label: str, data: FileData, columns: List[str], non_blank: List[str]) -> List[BenchmarkTest]:
    category = f"File format: {label}"
    tests = [
        BenchmarkTest(category, "File is a readable, non-empty CSV", _readable_check(data)),
        BenchmarkTest(category, f"Header has columns {columns}", _header_check(data, columns)),
    ]
    for column in non_blank:
        tests.append(BenchmarkTest(category, f"'{column}' is never blank", _column_check(data, column, _not_blank)))
    tests.append(BenchmarkTest(category, "'latitude' is a decimal in [-90, 90] for every record", _column_check(data, "latitude", _lat)))
    tests.append(BenchmarkTest(category, "'longitude' is a decimal in [-180, 180] for every record", _column_check(data, "longitude", _lon)))
    return tests


# ---- fixture tests --------------------------------------------------------- #

def _describe(inputs: Inputs, ref: StopRef) -> str:
    ids = inputs.ids[ref]
    return f"{ref[0]} / {ref[1]} -> {', '.join(sorted(ids))}"


def _resolve(t: unittest.TestCase, inputs: Inputs, fixture: Fixture) -> List[StopRef]:
    """Skip unless the fixture is populated and every stop is in the GTFS file."""
    if not inputs.gtfs_usable:
        t.skipTest("GTFS stops file is not usable (see file format tests)")
    if len(fixture.stops) < 2:
        t.skipTest("fixture not populated yet (needs at least 2 stops)")
    refs = [(n.strip(), s.strip()) for n, s in fixture.stops]
    absent = [r for r in refs if r not in inputs.ids]
    if absent:
        t.skipTest("stop(s) not in GTFS stops file: " + ", ".join(f"{n} / {s}" for n, s in absent))
    return refs


def _same_check(inputs: Inputs, fixture: Fixture):
    def check(t: unittest.TestCase):
        refs = _resolve(t, inputs, fixture)
        all_ids = set().union(*(inputs.ids[r] for r in refs))
        multi = [r for r in refs if len(inputs.ids[r]) > 1]
        if multi:
            t.fail("stop has more than one unique_id in file: " + "; ".join(_describe(inputs, r) for r in multi))
        if len(all_ids) > 1:
            spread = inputs.spread_m(refs)
            where = f" (stops are up to {spread:.0f} m apart)" if spread is not None else ""
            t.fail("expected one shared unique_id but got " + str(len(all_ids)) + where + ": "
                   + "; ".join(_describe(inputs, r) for r in refs))
    return check


def _different_check(inputs: Inputs, fixture: Fixture):
    def check(t: unittest.TestCase):
        refs = _resolve(t, inputs, fixture)
        multi = [r for r in refs if len(inputs.ids[r]) > 1]
        if multi:
            t.fail("stop has more than one unique_id in file: " + "; ".join(_describe(inputs, r) for r in multi))
        collisions = [
            (a, b) for a, b in combinations(refs, 2) if inputs.ids[a] & inputs.ids[b]
        ]
        if collisions:
            parts = []
            for a, b in collisions:
                spread = inputs.spread_m([a, b])
                dist = f", {spread:.0f} m apart" if spread is not None else ""
                parts.append(f"{a[0]} / {a[1]} and {b[0]} / {b[1]} share {', '.join(sorted(inputs.ids[a] & inputs.ids[b]))}{dist}")
            t.fail("expected distinct unique_ids but " + "; ".join(parts))
    return check


def fixture_tests(inputs: Inputs) -> List[BenchmarkTest]:
    tests = []
    for fx in SHOULD_MATCH_FIXTURES:
        tests.append(BenchmarkTest(f"Should match: {fx.category}", fx.name, _same_check(inputs, fx)))
    for fx in SHOULD_NOT_MATCH_FIXTURES:
        tests.append(BenchmarkTest(f"Should not match: {fx.category}", fx.name, _different_check(inputs, fx)))
    return tests


def build_suite(inputs: Inputs) -> unittest.TestSuite:
    tests: List[BenchmarkTest] = []
    tests += format_tests(DEDUP_LABEL, inputs.dedup, DEDUP_COLUMNS, ["unique_id"])
    tests += format_tests(GTFS_LABEL, inputs.gtfs, GTFS_COLUMNS, [GTFS_NAME, GTFS_STOP_ID, GTFS_UID])
    tests += fixture_tests(inputs)
    return unittest.TestSuite(tests)


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def _rate(passed: int, failed: int) -> str:
    graded = passed + failed
    return f"{100 * passed / graded:.1f}%" if graded else "n/a"


def summarise(outcomes: List[Outcome]):
    totals = {"passed": 0, "failed": 0, "skipped": 0}
    by_category: "OrderedDict[str, Dict[str, int]]" = OrderedDict()
    for o in outcomes:
        totals[o.status] += 1
        by_category.setdefault(o.category, {"passed": 0, "failed": 0, "skipped": 0})[o.status] += 1
    return totals, by_category


def print_report(outcomes: List[Outcome], label: str, dedup_path: str, gtfs_path: str, verbose: bool) -> None:
    totals, by_category = summarise(outcomes)
    total = len(outcomes)
    bar = "=" * 78
    print(bar)
    print(f"Shared stop benchmark: {label}")
    print(f"  deduplicated stops: {dedup_path}")
    print(f"  GTFS stops:         {gtfs_path}")
    print(bar)
    print(
        f"OVERALL  {total} tests | {totals['passed']} passed | {totals['failed']} failed | "
        f"{totals['skipped']} skipped | pass rate {_rate(totals['passed'], totals['failed'])} (skipped excluded)"
    )
    print()
    width = max([len("Category")] + [len(c) for c in by_category])
    print(f"{'Category'.ljust(width)}  {'Pass':>5} {'Fail':>5} {'Skip':>5} {'Rate':>7}")
    print(f"{'-' * width}  {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 7}")
    for category, c in by_category.items():
        print(f"{category.ljust(width)}  {c['passed']:>5} {c['failed']:>5} {c['skipped']:>5} {_rate(c['passed'], c['failed']):>7}")

    failures = [o for o in outcomes if o.status == "failed"]
    if failures:
        print("\nFAILURES")
        for o in failures:
            print(f"  [{o.category}] {o.name}\n      {o.message}")
    skipped = [o for o in outcomes if o.status == "skipped"]
    if skipped and verbose:
        print("\nSKIPPED")
        for o in skipped:
            print(f"  [{o.category}] {o.name}\n      {o.message}")
    elif skipped:
        print(f"\n{len(skipped)} test(s) skipped; rerun with --verbose to see why.")
    print()


def write_json(path: str, outcomes: List[Outcome], label: str, dedup_path: str, gtfs_path: str) -> None:
    totals, by_category = summarise(outcomes)
    payload = {
        "label": label,
        "inputs": {"deduplicated_stops": dedup_path, "gtfs_stops": gtfs_path},
        "overall": {**totals, "total": len(outcomes)},
        "categories": by_category,
        "tests": [o.__dict__ for o in outcomes],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark a shared transit stop identification algorithm against test cases.")
    parser.add_argument("--dedup", required=True, help="CSV of deduplicated stops (unique_id, latitude, longitude)")
    parser.add_argument("--gtfs", required=True, help="CSV of GTFS stops with the unique_id each was assigned")
    parser.add_argument("--label", default="unnamed algorithm", help="name of the algorithm being tested, shown in the report")
    parser.add_argument("--json", metavar="PATH", help="also write machine-readable results here")
    parser.add_argument("--verbose", "-v", action="store_true", help="list skipped tests and why")
    parser.add_argument("--fail-on-skipped", action="store_true", help="exit non-zero if any test was skipped")
    args = parser.parse_args(argv)

    inputs = Inputs(load_csv(args.dedup), load_csv(args.gtfs))
    result = BenchmarkResult()
    build_suite(inputs).run(result)

    print_report(result.outcomes, args.label, args.dedup, args.gtfs, args.verbose)
    if args.json:
        write_json(args.json, result.outcomes, args.label, args.dedup, args.gtfs)

    totals, _ = summarise(result.outcomes)
    if totals["failed"] or (args.fail_on_skipped and totals["skipped"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
