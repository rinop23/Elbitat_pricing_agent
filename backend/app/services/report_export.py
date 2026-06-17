"""Formatted Excel export shared by the Streamlit app and the weekly CLI report.

Produces a multi-sheet .xlsx with bold/frozen headers, autofilter, auto-fit column
widths and a euro number format on price columns.
"""
from __future__ import annotations

import io
from typing import Dict, Optional

import pandas as pd

# Columns that are numeric but NOT money (so we don't apply a euro format to them).
NON_MONEY_NUMERIC = {
    "nights", "guests_adults", "guests_children",
    "competitor_available_count", "competitor_total_count", "median_trend_pct",
}


def build_excel_report(sheets: Dict[str, Optional[pd.DataFrame]]) -> bytes:
    """Build a formatted multi-sheet .xlsx from {sheet_name: DataFrame}. Returns bytes."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        wb = writer.book
        header_fmt = wb.add_format({
            "bold": True, "bg_color": "#1F4E78", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        money_fmt = wb.add_format({"num_format": "€#,##0.00"})

        for raw_name, df in sheets.items():
            name = (str(raw_name)[:31]) or "Sheet"
            if df is None or len(df) == 0:
                pd.DataFrame({"info": ["No data for this filter"]}).to_excel(
                    writer, sheet_name=name, index=False
                )
                continue

            write_index = df.index.name is not None  # the price grid uses check_in as index
            df.to_excel(writer, sheet_name=name, index=write_index)
            ws = writer.sheets[name]
            offset = 1 if write_index else 0
            n_rows = df.shape[0]
            n_cols = df.shape[1] + offset

            if write_index:
                ws.write(0, 0, df.index.name, header_fmt)
            for c, col in enumerate(df.columns):
                ws.write(0, c + offset, str(col), header_fmt)

            ws.freeze_panes(1, 0)
            ws.autofilter(0, 0, n_rows, n_cols - 1)

            if write_index:
                idx_w = max([len(str(df.index.name or ""))] + [len(str(v)) for v in df.index]) + 2
                ws.set_column(0, 0, min(idx_w, 40))

            for c, col in enumerate(df.columns):
                series = df[col]
                width = max([len(str(col))] + [len(str(v)) for v in series.head(300)]) + 2
                is_money = (
                    pd.api.types.is_numeric_dtype(series)
                    and str(col).lower() not in NON_MONEY_NUMERIC
                )
                ws.set_column(c + offset, c + offset, min(width, 40), money_fmt if is_money else None)

    return buffer.getvalue()
