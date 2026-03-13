# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

**statera_vk** — Periodized strength training tracker for one client (Klotzbücher, Valentin) over ~17 months. Raw data lives in Excel spreadsheets; an ETL pipeline merges them into a panel dataset; a Quarto report visualizes progress. Published via GitHub Pages.

## Repository Structure

```
data/           Excel source files (.xls) + merged panel CSV
etl.py          Python ETL script (xlrd + pandas)
report.qmd      Quarto report source (Plotly charts)
report.html     Rendered self-contained HTML report
docs/index.html Copy of report.html served by GitHub Pages
requirements.txt Python dependencies
```

## Key Commands

- `python3 etl.py` — Parse all `data/*.xls` files → `data/training_panel.csv`
- `QUARTO_PYTHON=.venv/bin/python3 quarto render report.qmd --to html` — Render report
- After rendering, copy `report.html` to `docs/index.html` for GitHub Pages

## Notes

- The venv at `.venv/` uses Python 3.14; Quarto needs `QUARTO_PYTHON` set to use it
- Excel .xls files are binary and not diffable in git
- Phase numbering uses an "A" suffix starting from Phase 6
- Exercise name normalization is handled in `EXERCISE_NORM` dict in `etl.py`
