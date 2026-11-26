import csv
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from .common import CATEGORY_LABELS, CATEGORY_ORDER, MODE_LABELS, REPORT_BLUE, REPORT_BORDER, REPORT_NAVY, REPORT_PALE, TOPOLOGY_LABELS
from .results import aggregate_data, cartogram_data, load_artifacts

app = APIRouter()

def safe_cell(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value

def _report_video_parts(name):
    """Extract period and recording/circle number used by the supplied examples."""
    stem = Path(name).stem
    match = re.search(r"(?:^|[_\s-])(утро|вечер|выходной)(?:[_\s-]+)(\d+)",
                      stem, re.IGNORECASE)
    if not match:
        return "", ""
    return match.group(1).lower(), int(match.group(2))

def _style_table_sheet(page, freeze="A2", filter_table=True):
    """Apply restrained dark-blue report styling to a rectangular data sheet."""
    if page.max_row < 1 or page.max_column < 1:
        return
    dark = PatternFill("solid", fgColor=REPORT_NAVY)
    line = Side(style="thin", color=REPORT_BORDER)
    for cell in page[1]:
        cell.fill = dark
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = Border(bottom=line)
    for row in page.iter_rows(min_row=2):
        for cell in row:
            cell.font = Font(name="Arial", size=10, color="172033")
            cell.alignment = Alignment(vertical="center")
            cell.border = Border(bottom=Side(style="hair", color="E7EDF5"))
    page.freeze_panes = freeze
    if filter_table and page.max_row >= 2:
        page.auto_filter.ref = page.dimensions
    page.sheet_view.showGridLines = False
    page.row_dimensions[1].height = 28
    for column in range(1, page.max_column + 1):
        values = [str(page.cell(row, column).value or "") for row in range(1, page.max_row + 1)]
        page.column_dimensions[get_column_letter(column)].width = min(42, max(10, max(map(len, values)) + 2))

def _flow_groups(result, diagram):
    """Create one reconciled set of report directions without double-counting."""
    groups = defaultdict(Counter)
    labels = {}
    if result["geometry"].get("mode") == "automatic" and diagram["topology"] != "unknown":
        for row in diagram["direction_matrix"]:
            key = (row["direction"], row["from"], row["to"])
            labels[key] = f"Направление {row['direction']}\n{row['from']} → {row['to']}"
            groups[key][row["category"]] += row["count"]
        if diagram["unresolved"]:
            key = (10_000, "Не определено", "Не определено")
            labels[key] = "Направление не определено"
            for row in diagram["unresolved_by_category"]:
                groups[key][row["category"]] += row["count"]
    else:
        for row in result["matrix"]:
            key = (0, row["from"], row["to"])
            groups[key][row["category"]] += row["count"]
        ordered = sorted(groups, key=lambda key: (key[1], key[2]))
        groups = {key: groups[key] for key in ordered}
        labels = {key: f"Направление {index}\n{key[1]} → {key[2]}"
                  for index, key in enumerate(ordered, 1)}
    return [(key, labels[key], groups[key]) for key in groups]

def _add_count_sheet(book, result, diagram):
    """Add a wide two-level count matrix matching the supplied workbook convention."""
    page = book.create_sheet("Подсчёты")
    period, recording = _report_video_parts(result["video"]["name"])
    metadata = (("Видео", result["video"]["name"]), ("Сцена", result["scene"]["name"]),
                ("Период", period), ("Видео / круг", recording))
    for column, (heading, value) in enumerate(metadata, 1):
        page.merge_cells(start_row=1, start_column=column, end_row=2, end_column=column)
        page.cell(1, column, safe_cell(heading))
        page.cell(3, column, safe_cell(value))

    groups = _flow_groups(result, diagram)
    observed = {row["category"] for row in result["category_totals"]}
    categories = [category for category in CATEGORY_ORDER if category in observed]
    categories.extend(sorted(observed - set(categories)))
    if not categories:
        categories = list(CATEGORY_ORDER)
    column = 5
    for _, label, counts in groups:
        start = column
        end = column + len(categories) - 1
        if end > start:
            page.merge_cells(start_row=1, start_column=start, end_row=1, end_column=end)
        page.cell(1, start, safe_cell(label))
        for category in categories:
            page.cell(2, column, safe_cell(CATEGORY_LABELS.get(category, category)))
            page.cell(3, column, counts.get(category, 0))
            column += 1
    total_start = column
    total_end = column + len(categories) - 1
    if total_end > total_start:
        page.merge_cells(start_row=1, start_column=total_start, end_row=1, end_column=total_end)
    page.cell(1, total_start, "Итого")
    totals = {row["category"]: row["count"] for row in result["category_totals"]}
    for category in categories:
        page.cell(2, column, safe_cell(CATEGORY_LABELS.get(category, category)))
        page.cell(3, column, totals.get(category, 0))
        column += 1

    dark = PatternFill("solid", fgColor=REPORT_NAVY)
    blue = PatternFill("solid", fgColor=REPORT_BLUE)
    pale = PatternFill("solid", fgColor=REPORT_PALE)
    line = Side(style="thin", color="FFFFFF")
    for row in (1, 2):
        for cell in page[row]:
            cell.fill = dark if row == 1 else blue
            cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=line, right=line, bottom=line)
    for cell in page[3]:
        cell.fill = pale
        cell.font = Font(name="Arial", size=10, color="172033")
        cell.alignment = Alignment(horizontal="right" if cell.column >= 5 else "left",
                                   vertical="center")
        cell.border = Border(bottom=Side(style="thin", color=REPORT_BORDER))
    page.freeze_panes = "E3"
    page.sheet_view.showGridLines = False
    page.row_dimensions[1].height = 38
    page.row_dimensions[2].height = 26
    page.column_dimensions["A"].width = 30
    page.column_dimensions["B"].width = 24
    page.column_dimensions["C"].width = 14
    page.column_dimensions["D"].width = 14
    for index in range(5, page.max_column + 1):
        page.column_dimensions[get_column_letter(index)].width = 11
    page.print_title_rows = "1:2"
    page.print_title_cols = "A:D"
    page.page_setup.orientation = "landscape"
    page.page_setup.scale = 80
    return page

def _add_summary_sheet(book, result, diagram):
    page = book.create_sheet("Отчёт", 0)
    page["A2"] = "Отчёт по транспортным и пешеходным потокам"
    page["A2"].font = Font(name="Arial", size=15, bold=True, color=REPORT_NAVY)
    page.merge_cells("A2:F2")
    page["A3"] = "Результаты выбранного запуска анализа"
    page["A3"].font = Font(name="Arial", size=10, italic=True, color="52647A")
    page.merge_cells("A3:F3")
    page["A4"].fill = PatternFill("solid", fgColor=REPORT_BLUE)
    page.merge_cells("A4:F4")

    details = [
        ("Видео", result["video"]["name"]),
        ("Сцена", result["scene"]["name"]),
        ("Режим данных", MODE_LABELS.get(result["mode"], result["mode"])),
        ("Интервал", f"{result['interval_s']} с"),
        ("Тип узла", TOPOLOGY_LABELS.get(diagram["topology"], diagram["topology"])),
    ]
    for row, (label, value) in enumerate(details, 6):
        page.cell(row, 1, label)
        page.cell(row, 2, safe_cell(value))
        page.cell(row, 1).font = Font(name="Arial", size=10, bold=True, color=REPORT_NAVY)
        page.cell(row, 2).font = Font(name="Arial", size=10, color="172033")

    metrics = (("Всего учтено", result["total"]),
               ("Транспорт", result["transport_total"]),
               ("Пешеходы", result["pedestrian_total"]),
               ("Направление определено", diagram["routed"]),
               ("Направление не определено", diagram["unresolved"]))
    for row, (label, value) in enumerate(metrics, 6):
        page.cell(row, 4, label)
        page.cell(row, 5, value)
        page.cell(row, 4).fill = PatternFill("solid", fgColor=REPORT_PALE)
        page.cell(row, 5).fill = PatternFill("solid", fgColor=REPORT_PALE)
        page.cell(row, 4).font = Font(name="Arial", size=10, bold=True, color=REPORT_NAVY)
        page.cell(row, 5).font = Font(name="Arial", size=11, bold=True, color=REPORT_BLUE)
        page.cell(row, 5).alignment = Alignment(horizontal="right")

    page["A13"] = "По категориям"
    page["A13"].fill = PatternFill("solid", fgColor=REPORT_NAVY)
    page["B13"] = "Количество"
    page["B13"].fill = PatternFill("solid", fgColor=REPORT_NAVY)
    for cell in page[13][:2]:
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
    for row, item in enumerate(result["category_totals"], 14):
        page.cell(row, 1, safe_cell(CATEGORY_LABELS.get(item["category"], item["category"])))
        page.cell(row, 2, item["count"])

    page["D13"] = "Покрытие картограммы"
    page["D13"].fill = PatternFill("solid", fgColor=REPORT_NAVY)
    page["E13"] = "Значение"
    page["E13"].fill = PatternFill("solid", fgColor=REPORT_NAVY)
    for cell in (page["D13"], page["E13"]):
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center")
    coverage = (("Доля определённых", diagram["coverage"]),
                ("По движению в кадре", diagram["motion_estimated"]),
                ("По именованным линиям", diagram["user_directions"]))
    for row, (label, value) in enumerate(coverage, 14):
        page.cell(row, 4, label)
        page.cell(row, 5, value)
    page["E14"].number_format = "0.0%"

    note_row = max(20, 15 + len(result["category_totals"]))
    page.cell(note_row, 1, "Примечание")
    page.cell(note_row, 1).font = Font(name="Arial", size=10, bold=True, color=REPORT_NAVY)
    page.cell(note_row + 1, 1,
              "Номера направлений в листе «Подсчёты» относятся к сформированной схеме. "
              "Для сопоставления с нумерацией приложенной картограммы нужна явная привязка линий камеры.")
    page.merge_cells(start_row=note_row + 1, start_column=1, end_row=note_row + 2, end_column=6)
    page.cell(note_row + 1, 1).alignment = Alignment(wrap_text=True, vertical="top")
    page.cell(note_row + 1, 1).font = Font(name="Arial", size=10, color="52647A")
    page.sheet_view.showGridLines = False
    page.column_dimensions["A"].width = 27
    page.column_dimensions["B"].width = 32
    page.column_dimensions["C"].width = 4
    page.column_dimensions["D"].width = 29
    page.column_dimensions["E"].width = 16
    page.column_dimensions["F"].width = 4
    page.print_area = f"A1:F{note_row + 2}"
    page.page_setup.orientation = "landscape"
    page.page_setup.fitToWidth = 1
    page.page_setup.fitToHeight = 1
    page.sheet_properties.pageSetUpPr.fitToPage = True
    page.page_margins.left = 0.25
    page.page_margins.right = 0.25
    page.page_margins.top = 0.35
    page.page_margins.bottom = 0.35
    page.print_options.horizontalCentered = True
    return page

@app.get("/api/runs/{run_id}/export/{format}", tags=["Результаты"], summary="Скачать отчёт")
def export(run_id: str, format: str, mode: str = "effective", interval: int = 900):
    result = aggregate_data(run_id, mode, interval)
    clusters, performance = load_artifacts(result)
    if format == "json":
        return Response(json.dumps({**result, "cartogram": cartogram_data(result), "clusters": clusters, "performance": performance}, ensure_ascii=False), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'})
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(("from", "to", "category", "count"))
        for row in result["matrix"]:
            writer.writerow([safe_cell(row[key]) for key in ("from", "to", "category", "count")])
        return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{run_id}.csv"'})
    if format == "xlsx":
        diagram = cartogram_data(result)
        book = Workbook()
        book.remove(book.active)
        _add_summary_sheet(book, result, diagram)
        _add_count_sheet(book, result, diagram)
        for name, headings, records in (
            ("Summary", ("metric", "value"),
             [("video", result["video"]["name"]), ("scene", result["scene"]["name"]),
              ("total", result["total"]), ("transport", result["transport_total"]),
              ("pedestrians", result["pedestrian_total"]), ("mode", mode),
              ("interval_s", interval)]),
            ("Flow Matrix", ("from", "to", "category", "count"),
              [[row[k] for k in ("from", "to", "category", "count")] for row in result["matrix"]]),
            ("Cartogram estimate", ("from (schematic)", "to (schematic)", "category", "count"),
             [[row[k] for k in ("from", "to", "category", "count")] for row in diagram["matrix"]]),
            ("Cartogram coverage", ("metric", "value"),
             [("topology", diagram["topology"]), ("routed estimate", diagram["routed"]),
              ("motion estimated", diagram["motion_estimated"]),
              ("user directions", diagram["user_directions"]),
              ("unresolved", diagram["unresolved"]), ("all counted", diagram["total"])]),
            ("Intervals", ("start_s", "end_s", "category", "count"),
             [[row[k] for k in ("start_s", "end_s", "category", "count")] for row in result["intervals"]]),
            ("Events", ("id", "time_s", "from", "to", "category", "status", "origin",
                        "tracker_id", "confidence"),
             [[e.get(k) for k in ("id", "time_s", "from_direction", "to_direction", "category",
                                  "status", "origin", "tracker_id", "confidence")]
              for e in result["events"]]),
            ("Review", ("status", "count"), list(result["statuses"].items())),
        ):
            page = book.create_sheet(name)
            page.append(headings)
            for record in records:
                page.append([safe_cell(value) for value in record])
            _style_table_sheet(page)
        cluster_sheet = book.create_sheet("Кластеры")
        cluster_sheet.append(("cluster", "category", "count"))
        for row in clusters["counts"]:
            cluster_sheet.append((row["cluster"], row["category"], row["count"]))
        cluster_sheet.append(("unresolved", "all", clusters["unresolved_events"]))
        _style_table_sheet(cluster_sheet)
        if performance:
            performance_sheet = book.create_sheet("Производительность")
            performance_sheet.append(("metric", "value"))
            for key, value in performance.items():
                performance_sheet.append((key, safe_cell(json.dumps(value) if isinstance(value, dict) else value)))
            _style_table_sheet(performance_sheet)
        book.active = 0
        data = io.BytesIO()
        book.save(data)
        return Response(data.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{run_id}.xlsx"'})
    raise HTTPException(422, "Форматы: xlsx, csv, json")

