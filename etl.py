#!/usr/bin/env python3
"""ETL script to parse training spreadsheets into a panel dataset."""

import glob
import os
import re
from datetime import datetime

import pandas as pd
import xlrd

# Exercise name normalization mapping
EXERCISE_NORM = {
    "Bankdrüken": "Bankdrücken",
    "Kniebeuge Ma.": "Kniebeuge Maschine",
    "Kniebeugen": "Kniebeuge Maschine",
    "Schulterdrücken": "Schulterdrücken stehend",
    "Beinbeugen ": "Beinbeugen",
}

# Estimated dates for phases without dates (interpolated from known dates)
ESTIMATED_DATES = {
    5: "2025-03-03",  # ~6 weeks after Phase 4 (20.01.2025)
    6: "2025-04-14",  # ~6 weeks after Phase 5
    8: "2025-07-14",  # ~6 weeks after Phase 7A (02.06.2025)
    9: "2025-08-25",  # ~6 weeks after Phase 8A
}


def parse_phase_info(filename, sheet):
    """Extract phase name, number, and date from filename and sheet content."""
    basename = os.path.basename(filename).replace(".xls", "")

    phase_match = re.search(r"Phase\s+(\d+)A?", basename)
    if not phase_match:
        return basename, 0, None

    phase_name = re.search(r"Phase\s+\d+A?", basename).group(0)
    phase_num = int(phase_match.group(1))

    # Find date from cells (look for "Start: DD.MM.YYYY")
    date_str = None
    for r in range(min(sheet.nrows, 10)):
        for c in range(sheet.ncols):
            val = str(sheet.cell_value(r, c))
            m = re.search(r"Start:\s*(\d{2}\.\d{2}\.\d{4})", val)
            if m:
                date_str = m.group(1)
                break
        if date_str:
            break

    # Fallback: date in filename
    if not date_str:
        m = re.search(r"(\d{2}\.\d{2}\.\d{4})", basename)
        if m:
            date_str = m.group(1)

    phase_date = None
    if date_str:
        try:
            phase_date = datetime.strptime(date_str, "%d.%m.%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Use estimated date if none found
    if not phase_date and phase_num in ESTIMATED_DATES:
        phase_date = ESTIMATED_DATES[phase_num]

    return phase_name, phase_num, phase_date


def find_header_row(sheet):
    """Find the row containing 'Übung' header."""
    for r in range(sheet.nrows):
        for c in range(sheet.ncols):
            if str(sheet.cell_value(r, c)).strip() == "Übung":
                return r
    return None


def detect_columns(sheet, header_row):
    """Detect column layout and return column map + whether Sätze exists."""
    headers = [
        str(sheet.cell_value(header_row, c)).strip() for c in range(sheet.ncols)
    ]

    col_map = {}
    col_map["exercise"] = headers.index("Übung")
    col_map["settings"] = headers.index("Einst.")

    has_sets = "Sätze" in headers
    if has_sets:
        col_map["sets"] = headers.index("Sätze")

    for i, h in enumerate(headers):
        if h.startswith("Wdh"):
            col_map["reps"] = i
            break

    week_cols = {}
    for i, h in enumerate(headers):
        m = re.match(r"Woche\s+(\d+)", h)
        if m:
            week_cols[int(m.group(1))] = i
    col_map["weeks"] = week_cols

    for i, h in enumerate(headers):
        if h.upper().startswith("TYP"):
            col_map["type"] = i
            break

    for i, h in enumerate(headers):
        if "AMPRAP" in h.upper() or "AMRAP" in h.upper():
            col_map["amrap"] = i
            break

    for i, h in enumerate(headers):
        if h.strip().upper() == "TR":
            col_map["tr"] = i
            break

    return col_map, has_sets


def parse_weight(val):
    """Parse weight value from various formats (e.g. '75kg', '22,5', 80.0)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val != 0 or isinstance(val, (int, float)) else None

    s = str(val).strip()
    if s == "":
        return None

    s = re.sub(r"\s*kg\s*$", "", s, flags=re.IGNORECASE)
    s = s.replace(",", ".")

    try:
        return float(s)
    except ValueError:
        return None


def normalize_exercise(name):
    """Normalize exercise name to canonical form."""
    name = name.strip()
    return EXERCISE_NORM.get(name, name)


def safe_cell(sheet, r, c):
    """Safely get cell value, returning '' for out-of-bounds."""
    if c < 0 or c >= sheet.ncols or r < 0 or r >= sheet.nrows:
        return ""
    return sheet.cell_value(r, c)


def safe_str(val):
    """Convert cell value to clean string representation."""
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return str(val)
    return str(val).strip()


def is_exercise_row(sheet, r, exercise_col):
    """Check if a row contains exercise data (not instructions/notes)."""
    val = str(sheet.cell_value(r, exercise_col)).strip()
    if val == "" or val.startswith("Plan"):
        return False
    if val.startswith("In jedem") or re.match(r"^\d+\.\s", val):
        return False
    # Filter out instruction text rows at bottom of sheets
    skip_prefixes = ("AMPRAP", "Ergebnisse", "Es werden")
    if val.startswith(skip_prefixes):
        return False
    return True


def parse_file(filepath):
    """Parse a single Excel file into rows of long-format data."""
    wb = xlrd.open_workbook(filepath)
    sheet = wb.sheet_by_index(0)

    phase_name, phase_num, phase_date = parse_phase_info(filepath, sheet)
    header_row = find_header_row(sheet)
    if header_row is None:
        print(f"WARNING: No header found in {filepath}")
        return []

    col_map, has_sets = detect_columns(sheet, header_row)

    # Determine if this file has explicit Plan A/B markers
    has_plan_a = False
    has_plan_b = False
    for r in range(header_row + 1, sheet.nrows):
        val = str(sheet.cell_value(r, 0)).strip()
        if val.startswith("Plan A"):
            has_plan_a = True
        if val.startswith("Plan B"):
            has_plan_b = True

    rows = []
    current_plan = "single"
    if has_plan_a:
        current_plan = None  # will be set on Plan A marker

    consecutive_blanks = 0

    for r in range(header_row + 1, sheet.nrows):
        first_cell = str(sheet.cell_value(r, 0)).strip()

        # Plan markers
        if first_cell.startswith("Plan A"):
            current_plan = "A"
            consecutive_blanks = 0
            continue
        if first_cell.startswith("Plan B"):
            current_plan = "B"
            consecutive_blanks = 0
            continue

        # Track blank rows for implicit Plan B detection
        if not is_exercise_row(sheet, r, col_map["exercise"]):
            consecutive_blanks += 1
            # Phases with Plan A but no explicit Plan B: double blank = switch to B
            if (
                has_plan_a
                and not has_plan_b
                and consecutive_blanks >= 2
                and current_plan == "A"
            ):
                current_plan = "B"
            continue

        consecutive_blanks = 0

        if current_plan is None:
            current_plan = "single"

        exercise = first_cell
        settings = str(safe_cell(sheet, r, col_map["settings"])).strip()

        if has_sets:
            sets_raw = safe_cell(sheet, r, col_map["sets"])
            try:
                sets = str(int(float(sets_raw))) if sets_raw != "" else ""
            except (ValueError, TypeError):
                sets = safe_str(sets_raw)
        else:
            sets = ""

        reps_raw = safe_cell(sheet, r, col_map["reps"])
        try:
            reps = str(int(float(reps_raw))) if reps_raw != "" else ""
        except (ValueError, TypeError):
            reps = safe_str(reps_raw)

        type_raw = safe_cell(sheet, r, col_map["type"]) if "type" in col_map else ""
        try:
            type_str = str(int(float(type_raw))) if type_raw != "" else ""
        except (ValueError, TypeError):
            type_str = safe_str(type_raw)

        amrap_raw = safe_cell(sheet, r, col_map["amrap"]) if "amrap" in col_map else ""
        amrap = safe_str(amrap_raw)

        tr_raw = safe_cell(sheet, r, col_map["tr"]) if "tr" in col_map else ""
        tr = safe_str(tr_raw)

        for week_num, week_col in col_map["weeks"].items():
            weight_raw = safe_cell(sheet, r, week_col)
            weight = parse_weight(weight_raw)

            rows.append(
                {
                    "phase": phase_name,
                    "phase_num": phase_num,
                    "phase_date": phase_date,
                    "plan": current_plan,
                    "exercise": exercise,
                    "exercise_normalized": normalize_exercise(exercise),
                    "settings": settings,
                    "sets": sets,
                    "reps": reps,
                    "week": week_num,
                    "weight_kg": weight,
                    "type": type_str,
                    "amrap": amrap,
                    "tr": tr,
                }
            )

    return rows


def main():
    files = sorted(glob.glob("data/*.xls"))
    print(f"Found {len(files)} Excel files")

    all_rows = []
    for f in files:
        print(f"  Parsing: {f}")
        file_rows = parse_file(f)
        all_rows.extend(file_rows)
        print(f"    → {len(file_rows)} rows")

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["phase_num", "plan", "exercise", "week"]).reset_index(
        drop=True
    )

    os.makedirs("data", exist_ok=True)
    df.to_csv("data/training_panel.csv", index=False)

    print(f"\nTotal: {len(df)} rows")
    print(f"Phases: {df['phase'].nunique()}")
    print(f"Exercises: {df['exercise_normalized'].nunique()}")
    print(f"Saved to data/training_panel.csv")


if __name__ == "__main__":
    main()
