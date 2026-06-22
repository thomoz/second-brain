import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import pdfplumber
from pathlib import Path

# Target the monthly fund reports specifically
targets = [
    "O:/AI/Dynamous/Courses/second-brain-workshop/investments/briefs-finance/reports/holdings/1779425553-Briefs_Finance_Monthly_Fund_Report_January 2026.pdf",
    "O:/AI/Dynamous/Courses/second-brain-workshop/investments/briefs-finance/reports/holdings/1781831494-Briefs_Finance_Monthly_Fund_Report___Print-8 May 2026.pdf",
]

for path in targets:
    print(f"\n{'='*60}")
    print(f"FILE: {Path(path).name}")
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            images = page.images
            print(f"\n  Page {i+1}: {len(words)} words, {len(images)} images")
            if words:
                for w in words:
                    print(f"    x0={w['x0']:.0f} top={w['top']:.0f} | {w['text']}")
            for img in images:
                print(f"    IMAGE x0={img['x0']:.0f} top={img['top']:.0f} w={img['width']:.0f} h={img['height']:.0f}")
