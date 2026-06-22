from pathlib import Path

p = Path(r'O:\AI\Dynamous\Courses\second-brain-workshop\.agent\plans\briefs-finance-investment-tool.md')
text = p.read_text(encoding='utf-8')

# 1. Update pyproject deps to add rich
text = text.replace(
    '    "python-dateutil>=2.9.0",\n  ]\n  [project.optional-dependencies]',
    '    "python-dateutil>=2.9.0",\n    "rich>=13.0.0",\n  ]\n  [project.optional-dependencies]'
)

# 2. Add report.py and assessments/ to file list
text = text.replace(
    '    main.py                         # unified CLI\n    tests/',
    '    report.py                       # output layer: rich terminal + markdown vault + HTML\n    templates/\n      stats.html                    # Chart.js template for track record dashboard\n    tests/'
)
text = text.replace(
    '  principles/',
    '  assessments/                      # markdown assessment outputs written to vault\n  principles/'
)

# 3. Insert Task 14a before Task 14 (main.py)
new_task = '''
### Task 14a: CREATE investments/briefs-finance/scripts/report.py

- **IMPLEMENT**: Output layer — three modes selectable via --output flag or default.

  **Mode 1: Rich terminal (default)**
  Use ich.console.Console, ich.table.Table, ich.panel.Panel.
  ssess output: Panel header with score + provisional flag, Table for score breakdown,
  Table for sector context, Table for macro snapshot, Table for principles.
  stats output: Table of sector accuracy, bar-style progress columns for % beat S&P 500.
  `python
  from rich.console import Console
  from rich.table import Table
  from rich.panel import Panel
  console = Console()
  `

  **Mode 2: Markdown vault output (--output markdown)**
  Write assessment to investments/briefs-finance/assessments/{ticker}-{date}.md.
  Format: frontmatter (type, ticker, score, date), then full assess content as markdown.
  Also append a one-line summary to Memory/topics/investment-strategy.md (creates file if absent).
  `
  ## BABA - June 2026 | Score: 71% (PROVISIONAL)
  ...full assessment...
  `

  **Mode 3: HTML report (--output html)**
  Used by stats command only. Renders 	emplates/stats.html with Chart.js.
  Inject DB data as JSON into the template (Jinja2-style string replace or f-string).
  Charts: (a) % beating S&P 500 by sector (horizontal bar), (b) score distribution histogram,
  (c) top 10 / bottom 10 performers table.
  Open with webbrowser.open(output_path) after writing.
  Write to investments/briefs-finance/assessments/stats-{date}.html.

  `python
  def render_terminal(data: dict) -> None: ...
  def render_markdown(data: dict, ticker: str) -> Path: ...
  def render_html_stats(stats_data: dict) -> Path: ...
  `

- **GOTCHA**: webbrowser.open() on Windows opens the default browser — no server needed.
- **GOTCHA**: Memory/topics/investment-strategy.md may already exist. Use append mode,
  prepend a dated section header if it does. Never overwrite existing content.
- **GOTCHA**: HTML template uses Chart.js from CDN — no local JS files needed. Template is a
  static string with {{LABELS}}, {{DATA}} placeholders replaced at render time.
- **VALIDATE**: uv run python -m scripts.main assess --ticker KGC (rich terminal)
  uv run python -m scripts.main assess --ticker KGC --output markdown (check file written)
  uv run python -m scripts.main stats --output html (check browser opens)

'''
text = text.replace(
    '### Task 14: CREATE investments/briefs-finance/scripts/main.py',
    new_task + '### Task 14: CREATE investments/briefs-finance/scripts/main.py'
)

# 4. Update main.py task to reference report.py and add --output flag
text = text.replace(
    '  assess   --ticker T          # primary command: full output for new report evaluation\n  context  --ticker T          # sector ETF + macro at time of recommendation(s)',
    '  assess   --ticker T [--output terminal|markdown|html]  # full evaluation output\n  context  --ticker T          # sector ETF + macro at time of recommendation(s)'
)
text = text.replace(
    '  ssess output format (shown to Shaun for review):\n  `',
    '  Delegate all output rendering to eport.py. Pass --output flag through.\n  ssess terminal output via rich (shown to Shaun for review):\n  `'
)

# 5. Add display criteria to acceptance criteria
text = text.replace(
    '- [ ] SKILL.md has valid YAML frontmatter with correct CLI command references',
    '- [ ] SKILL.md has valid YAML frontmatter with correct CLI command references\n- [ ] ssess --ticker KGC renders rich terminal output with coloured panels and tables\n- [ ] ssess --ticker KGC --output markdown writes file to assessments/ and appends to investment-strategy.md\n- [ ] stats --output html generates HTML file and opens in browser with Chart.js charts'
)

# 6. Add test_report.py to test list
text = text.replace(
    '  	est_score.py (mock DB + LLM):\n    - 	est_score_in_range() -- always 0-100',
    '  	est_report.py:\n    - 	est_render_markdown_writes_file() -- check file created with frontmatter\n    - 	est_render_markdown_appends_to_investment_strategy() -- check vault file updated\n    - 	est_render_html_stats_creates_file() -- check HTML file written\n\n  	est_score.py (mock DB + LLM):\n    - 	est_score_in_range() -- always 0-100'
)

# 7. Add rich + output layer to notes
text = text.replace(
    '**OCR deferred**:',
    '**Output modes**: Default is rich terminal (no flag needed). Add --output markdown to save\nassessment to vault and append summary to Memory/topics/investment-strategy.md. Add\n--output html to the stats command to open a Chart.js dashboard in the browser.\n\n**OCR deferred**:'
)

p.write_text(text, encoding='utf-8')
lines = len(text.splitlines())
print(f'Done - {lines} lines')
