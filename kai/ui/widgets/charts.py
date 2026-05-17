"""Thin themed wrappers around PySide6 QtCharts."""
from __future__ import annotations

from datetime import datetime

from kai.ui import theme

from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries, QScatterSeries, QDateTimeAxis, QValueAxis,
)
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QPainter, QColor, QPen


def _qdatetime(iso: str) -> QDateTime:
    try:
        dt = datetime.fromisoformat(iso)
        return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    except (ValueError, TypeError):
        return QDateTime.currentDateTime()


def make_price_chart(
    snapshots: list[dict],
    title: str = "",
    show_original: bool = True,
) -> QChartView:
    """Return a themed QChartView showing current (and optionally original) price over time."""
    t = theme.theme()

    current_series = QLineSeries()
    current_series.setName("Price")
    original_series = QLineSeries()
    original_series.setName("Original")

    pen_cur = QPen(QColor(t.accent))
    pen_cur.setWidth(2)
    current_series.setPen(pen_cur)

    pen_orig = QPen(QColor(t.text_dim))
    pen_orig.setWidth(1)
    pen_orig.setStyle(Qt.PenStyle.DashLine)
    original_series.setPen(pen_orig)

    special_series = QScatterSeries()
    special_series.setName("On Special")
    special_series.setMarkerSize(10)
    special_series.setColor(QColor(t.success))
    special_series.setBorderColor(QColor(t.success))

    has_original = False
    has_specials = False
    for snap in snapshots:
        dt = _qdatetime(snap.get("date", ""))
        ms = dt.toMSecsSinceEpoch()
        cur = snap.get("current_price")
        orig = snap.get("original_price")
        on_special = snap.get("on_special", False)
        if cur is not None:
            current_series.append(ms, float(cur))
            if on_special:
                special_series.append(ms, float(cur))
                has_specials = True
        if orig is not None and orig != cur:
            original_series.append(ms, float(orig))
            has_original = True

    chart = QChart()
    chart.setBackgroundBrush(QColor(t.card))
    chart.setPlotAreaBackgroundBrush(QColor(t.bg))
    chart.setPlotAreaBackgroundVisible(True)
    chart.legend().setVisible((has_original and show_original) or has_specials)
    chart.legend().setLabelColor(QColor(t.text_dim))
    chart.setMargins(_margins(8))
    if title:
        chart.setTitle(title)
        chart.setTitleBrush(QColor(t.text))

    chart.addSeries(current_series)
    if has_original and show_original:
        chart.addSeries(original_series)
    if has_specials:
        chart.addSeries(special_series)

    # X axis — dates
    x_axis = QDateTimeAxis()
    x_axis.setFormat("d MMM yy")
    x_axis.setLabelsColor(QColor(t.text_dim))
    x_axis.setGridLineColor(QColor(t.border))
    chart.addAxis(x_axis, Qt.AlignmentFlag.AlignBottom)
    current_series.attachAxis(x_axis)
    if has_original and show_original:
        original_series.attachAxis(x_axis)
    if has_specials:
        special_series.attachAxis(x_axis)

    # Y axis — price
    y_axis = QValueAxis()
    y_axis.setLabelFormat("$%.2f")
    y_axis.setLabelsColor(QColor(t.text_dim))
    y_axis.setGridLineColor(QColor(t.border))
    chart.addAxis(y_axis, Qt.AlignmentFlag.AlignLeft)
    current_series.attachAxis(y_axis)
    if has_original and show_original:
        original_series.attachAxis(y_axis)
    if has_specials:
        special_series.attachAxis(y_axis)

    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    return view


def make_bar_chart_view(
    labels: list[str],
    values: list[float],
    title: str = "",
) -> QChartView:
    """Horizontal label→value bar chart as a simple line-series workaround using QLineSeries."""
    from PySide6.QtCharts import QBarSeries, QBarSet, QBarCategoryAxis

    t = theme.theme()

    bar_set = QBarSet("Cost")
    bar_set.setColor(QColor(t.accent))
    bar_set.setLabelColor(QColor(t.text))
    for v in values:
        bar_set.append(v)

    series = QBarSeries()
    series.append(bar_set)
    series.setLabelsVisible(True)
    series.setLabelsFormat("$@value")
    series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)

    chart = QChart()
    chart.setBackgroundBrush(QColor(t.card))
    chart.setPlotAreaBackgroundBrush(QColor(t.bg))
    chart.setPlotAreaBackgroundVisible(True)
    chart.legend().setVisible(False)
    chart.setMargins(_margins(8))
    chart.addSeries(series)
    if title:
        chart.setTitle(title)
        chart.setTitleBrush(QColor(t.text))

    cat_axis = QBarCategoryAxis()
    cat_axis.append(labels)
    cat_axis.setLabelsColor(QColor(t.text_dim))
    chart.addAxis(cat_axis, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(cat_axis)

    val_axis = QValueAxis()
    val_axis.setLabelFormat("$%.2f")
    val_axis.setLabelsColor(QColor(t.text_dim))
    val_axis.setGridLineColor(QColor(t.border))
    chart.addAxis(val_axis, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(val_axis)

    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    return view


def _margins(px: int):
    from PySide6.QtCore import QMargins
    return QMargins(px, px, px, px)
