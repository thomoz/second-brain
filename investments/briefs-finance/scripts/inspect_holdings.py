import pdfplumber
from pathlib import Path

REPORTS = Path("O:/AI/Dynamous/Courses/second-brain-workshop/investments/briefs-finance/reports/holdings")

for path in sorted(REPORTS.glob("*.pdf"))[:2]:
    print(f"\n{'='*60}")
    print(f"FILE: {path.name}")
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            images = page.images
            print(f"\n  Page {i+1}: {len(words)} words, {len(images)} images/objects")
            for w in words:
                print(f"    x0={w['x0']:.0f} top={w['top']:.0f} | {w['text']}")
            for img in images:
                print(f"    IMAGE: x0={img['x0']:.0f} top={img['top']:.0f} w={img['width']:.0f} h={img['height']:.0f}")
