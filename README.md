# Statera VK — Training Progress Tracker

Periodized strength training data for one client over ~17 months (Oct 2024 – Feb 2026), with an interactive dashboard visualizing progressive overload across 12 training phases.

**[View the live report](https://valentinklotzbuecher.github.io/statera_vk/)**

## What's in the report

- **Weight progression** — Week 1 starting weights + all weekly weights per exercise across all phases
- **Weekly ramp** — Intra-phase weight increases faceted by phase
- **Strength gains heatmap** — Percentage change from baseline for every exercise
- **Phase summary table** — Dates, exercise counts, rep schemes

## How it works

1. **`etl.py`** parses 12 Excel spreadsheets (`.xls`) into a normalized long-format panel dataset (`data/training_panel.csv`)
2. **`report.qmd`** renders an interactive Quarto HTML report with Plotly charts

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run ETL (requires .xls files in data/)
python3 etl.py

# Render report
QUARTO_PYTHON=.venv/bin/python3 quarto render report.qmd --to html
```

## Built with

[Claude Code](https://anthropic.skilljar.com/claude-code-in-action)
