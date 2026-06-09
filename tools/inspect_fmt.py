# -*- coding: utf-8 -*-
"""원본 .xls 서식(채움색/폰트/테두리/숫자서식/열너비) 덤프 — postprocess 서식 맞추기용."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import xlrd

f = r"C:\Users\777la\OneDrive\바탕 화면\한국보건안전대구교육원_260501~260531.xls"
if not Path(f).exists():
    # 폴백: 바탕화면/다운로드에서 가장 최근 .xls
    cands = []
    for d in (Path.home() / "OneDrive" / "바탕 화면", Path.home() / "Desktop", Path.home() / "Downloads"):
        if d.exists():
            cands += list(d.glob("*.xls"))
    if cands:
        f = str(max(cands, key=lambda p: p.stat().st_mtime))
print("file:", f)

wb = xlrd.open_workbook(f, formatting_info=True)
sh = wb.sheet_by_index(0)
print("dims", sh.nrows, sh.ncols)
print("colwidths:", [sh.computed_column_width(c) for c in range(sh.ncols)])
print("merged:", sh.merged_cells)


def desc(r, c):
    xf = wb.xf_list[sh.cell_xf_index(r, c)]
    fnt = wb.font_list[xf.font_index]
    nf = wb.format_map.get(xf.format_key)
    return {
        "bold": fnt.bold, "fontht": fnt.height, "fontcol": fnt.colour_index,
        "fillpat": xf.background.fill_pattern,
        "patcol": xf.background.pattern_colour_index,
        "bgcol": xf.background.background_colour_index,
        "border_tblr": (xf.border.top_line_style, xf.border.bottom_line_style,
                        xf.border.left_line_style, xf.border.right_line_style),
        "numfmt": (nf.format_str if nf else None),
        "halign": xf.alignment.hor_align,
    }


for (r, c, tag) in [(0, 0, "title"), (1, 0, "건수라벨"), (1, 3, "건수합계"),
                    (2, 0, "헤더No"), (2, 4, "헤더카드사"), (2, 8, "헤더매입"),
                    (3, 4, "데이터카드사"), (3, 8, "데이터매입"), (3, 0, "데이터No")]:
    print(f"[{tag}] r{r}c{c}:", desc(r, c))

# 등장하는 색 인덱스 → RGB
idxs = set()
for r in (1, 2, 3):
    for c in range(sh.ncols):
        d = desc(r, c)
        idxs.add(d["patcol"]); idxs.add(d["bgcol"]); idxs.add(d["fontcol"])
print("colour_map:", {i: wb.colour_map.get(i) for i in sorted(idxs)})
