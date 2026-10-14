"""Splice results/report_data.json into report.template.html -> report.html (the artifact source)."""

from pathlib import Path

HERE = Path(__file__).parent
template = (HERE / "report.template.html").read_text(encoding="utf-8")
data_json = (HERE / "results" / "report_data.json").read_text(encoding="utf-8")

out = template.replace("/*__DATA_JSON__*/null", data_json)
assert out != template, "placeholder not found"

(HERE / "report.html").write_text(out, encoding="utf-8")
print("Wrote", HERE / "report.html", "-", len(out) / 1024, "KB")
