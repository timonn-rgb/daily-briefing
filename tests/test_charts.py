from briefing.charts import line_chart_svg, sparkline_svg


def test_sparkline_trend_class_and_points():
    svg = sparkline_svg([1.0, 3.0, 2.0])
    assert svg.startswith('<svg class="spark up"')
    assert svg.count(",") == 3  # three x,y pairs
    assert 'class="spark down"' in sparkline_svg([3.0, 1.0])


def test_too_few_points_gives_empty_string():
    assert sparkline_svg([1.0]) == ""
    assert line_chart_svg([["2026-09-25", 1.0]], "x") == ""


def test_flat_series_does_not_divide_by_zero():
    assert "polyline" in sparkline_svg([5.0, 5.0, 5.0])
    assert "polyline" in line_chart_svg([["a", 5.0], ["b", 5.0]], "flat")


def test_line_chart_labels_and_escaping():
    svg = line_chart_svg([["2026-08-14", 5500.0], ["2026-09-25", 5712.3]], "S&P 500 <30d>")
    assert 'aria-label="S&amp;P 500 &lt;30d&gt;"' in svg
    assert ">5,712<" in svg and ">5,500<" in svg
    assert ">2026-08-14<" in svg and ">2026-09-25<" in svg
