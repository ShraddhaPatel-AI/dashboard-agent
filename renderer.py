"""
renderer.py
The deterministic engine: reads a validated JSON spec, aggregates the data,
and produces a single standalone HTML dashboard file.

"Deterministic" means no AI is involved here. Given the same spec, this module
always produces the same dashboard. This is intentional — the AI's job (deciding
WHAT to build) is fully separated from the renderer's job (building it).

How it works:
  1. Load the three CSV files (policies, quotes, claims) into pandas DataFrames.
  2. For each chart in the spec, filter the data by time range, compute the
     requested metric (e.g. count of claims, conversion rate), and group by
     the requested dimension (e.g. by state, by product).
  3. Convert each aggregated DataFrame to a Plotly chart (bar, line, or pie).
  4. Arrange the charts into rows using the spec's layout grid.
  5. Write everything into a single self-contained HTML file that includes
     the Plotly charting library — no server required, can be emailed or shared.

The spec is the "contract": renderer.py trusts the spec has already been
validated by validator.py before being passed here.

Usage:
    python renderer.py specs/example_spec_1.json
    python renderer.py specs/example_spec_2.json

Output lands in the output/ folder with the same name as the spec file.
"""

import sys
import json
import os
from datetime import datetime
import pandas as pd
import plotly.express as px
import plotly.io as pio


# ── DATA LOADING ──────────────────────────────────────────────────────────────
# Load all three source tables once at the start of every render call.
# Keeping them in a single dict makes it easy to pass all three tables to
# any metric function without needing global variables.

def load_data() -> dict:
    """Load all three CSV files into a dictionary of DataFrames."""
    return {
        'policies': pd.read_csv('data/policies.csv', parse_dates=['effective_date', 'expiry_date']),
        'quotes':   pd.read_csv('data/quotes.csv',   parse_dates=['quote_date']),
        'claims':   pd.read_csv('data/claims.csv',   parse_dates=['claim_date']),
    }


# ── TIME FILTERING ────────────────────────────────────────────────────────────

# Fixed reference "today" — matches the dataset's generation date
TODAY = pd.Timestamp('2026-09-28')

def apply_time_filter(df: pd.DataFrame, date_col: str, time_range: str) -> pd.DataFrame:
    """Narrow a DataFrame to rows within the requested time window."""
    if time_range == 'last_6_months':
        cutoff = TODAY - pd.DateOffset(months=6)
        return df[df[date_col] >= cutoff]
    elif time_range == 'this_year':
        return df[df[date_col].dt.year == TODAY.year]
    elif time_range == 'last_year':
        return df[df[date_col].dt.year == (TODAY.year - 1)]
    elif time_range == 'last_2_years':
        cutoff = TODAY - pd.DateOffset(years=2)
        return df[df[date_col] >= cutoff]
    return df  # 'all' — no filter


# ── METRIC COMPUTATION ────────────────────────────────────────────────────────
# This is the data processing core. Each metric is a specific calculation
# (count of rows, sum of a column, ratio of two groups) applied to one of
# the three source tables, optionally filtered to a date window.
#
# The special 'month_product' grouping creates a multi-column result (month + product)
# used for time-series line charts that break down trends by product type.
# Every metric branch handles this case explicitly to avoid a KeyError.

def compute_metric(data: dict, chart: dict) -> pd.DataFrame:
    """
    Aggregate the data for one chart based on its metric and grouping.
    Returns a DataFrame with the grouping column(s) plus a 'value' column.
    """
    metric     = chart['metric']
    grouping   = chart['grouping']
    time_range = chart['time_range']
    sort_order = chart.get('sort_order', 'none')

    # ── count of quotes ──────────────────────────────────────────────────────
    if metric == 'count_quotes':
        df = apply_time_filter(data['quotes'], 'quote_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['quote_date'].dt.to_period('M').astype(str)
            result = df.groupby(['month', 'product']).size().reset_index(name='value')
        else:
            result = df.groupby(grouping).size().reset_index(name='value')

    # ── what % of quotes converted to policies ───────────────────────────────
    elif metric == 'conversion_rate':
        df = apply_time_filter(data['quotes'], 'quote_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['quote_date'].dt.to_period('M').astype(str)
            total  = df.groupby(['month', 'product']).size()
            bound  = df[df['status'] == 'bound'].groupby(['month', 'product']).size()
            rate   = (bound / total * 100).fillna(0).round(1)
            result = rate.reset_index()
            result.columns = ['month', 'product', 'value']
        else:
            total  = df.groupby(grouping).size()
            bound  = df[df['status'] == 'bound'].groupby(grouping).size()
            rate   = (bound / total * 100).fillna(0).round(1)
            result = rate.reset_index()
            result.columns = [grouping, 'value']

    # ── total annual premium written ─────────────────────────────────────────
    elif metric == 'sum_premium':
        df = apply_time_filter(data['policies'], 'effective_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['effective_date'].dt.to_period('M').astype(str)
            result = (
                df.groupby(['month', 'product'])['annual_premium']
                .sum().round(2).reset_index(name='value')
            )
        else:
            result = (
                df.groupby(grouping)['annual_premium']
                .sum().round(2).reset_index(name='value')
            )

    # ── count of claims ───────────────────────────────────────────────────────
    elif metric == 'count_claims':
        df = apply_time_filter(data['claims'], 'claim_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['claim_date'].dt.to_period('M').astype(str)
            result = df.groupby(['month', 'product']).size().reset_index(name='value')
        elif grouping == 'claim_type':
            result = df.groupby('claim_type').size().reset_index(name='value')
        else:
            result = df.groupby(grouping).size().reset_index(name='value')

    # ── total claim dollars ───────────────────────────────────────────────────
    elif metric == 'sum_claim_amount':
        df = apply_time_filter(data['claims'], 'claim_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['claim_date'].dt.to_period('M').astype(str)
            result = (
                df.groupby(['month', 'product'])['claim_amount']
                .sum().round(2).reset_index(name='value')
            )
        elif grouping == 'claim_type':
            result = df.groupby('claim_type')['claim_amount'].sum().round(2).reset_index(name='value')
        else:
            result = df.groupby(grouping)['claim_amount'].sum().round(2).reset_index(name='value')

    # ── average claim dollars ─────────────────────────────────────────────────
    elif metric == 'avg_claim_amount':
        df = apply_time_filter(data['claims'], 'claim_date', time_range)
        if grouping == 'month_product':
            df = df.copy()
            df['month'] = df['claim_date'].dt.to_period('M').astype(str)
            result = (
                df.groupby(['month', 'product'])['claim_amount']
                .mean().round(2).reset_index(name='value')
            )
        else:
            result = (
                df.groupby(grouping)['claim_amount']
                .mean().round(2).reset_index(name='value')
            )

    else:
        raise ValueError(f"Unknown metric: '{metric}'. Check spec_format.md for valid options.")

    # Apply sort (skip for time-series grouping — always chronological)
    if sort_order == 'desc' and grouping != 'month_product':
        result = result.sort_values('value', ascending=False).reset_index(drop=True)
    elif sort_order == 'asc' and grouping != 'month_product':
        result = result.sort_values('value', ascending=True).reset_index(drop=True)

    return result


# ── CHART CREATION ────────────────────────────────────────────────────────────

Y_AXIS_LABELS = {
    'count_quotes':     'Number of Quotes',
    'conversion_rate':  'Conversion Rate (%)',
    'sum_premium':      'Total Premium ($)',
    'count_claims':     'Number of Claims',
    'sum_claim_amount': 'Total Claim Amount ($)',
    'avg_claim_amount': 'Average Claim Amount ($)',
}

# Color-blind-friendly palette
COLORS = px.colors.qualitative.Set2


def create_chart_html(df: pd.DataFrame, chart: dict, include_plotlyjs: bool) -> str:
    """
    Convert an aggregated DataFrame into a Plotly chart and return its HTML snippet.
    include_plotlyjs=True on the first chart only — embeds the ~3 MB Plotly library once.
    """
    chart_type = chart['chart_type']
    title      = chart['title']
    metric     = chart['metric']
    grouping   = chart['grouping']
    y_label    = Y_AXIS_LABELS.get(metric, 'Value')

    if chart_type == 'bar':
        if grouping == 'month_product':
            fig = px.bar(
                df, x='month', y='value', color='product',
                barmode='group',
                title=title,
                labels={'month': 'Month', 'value': y_label, 'product': 'Product'},
                color_discrete_sequence=COLORS,
                template='plotly_white',
            )
            fig.update_xaxes(tickangle=-45)
        else:
            x_col   = grouping if grouping != 'claim_type' else 'claim_type'
            x_label = x_col.replace('_', ' ').title()
            fig = px.bar(
                df, x=x_col, y='value',
                title=title,
                labels={x_col: x_label, 'value': y_label},
                color_discrete_sequence=COLORS,
                template='plotly_white',
            )
        fig.update_traces(marker_line_width=0)

    elif chart_type == 'line':
        if grouping == 'month_product':
            fig = px.line(
                df, x='month', y='value', color='product',
                title=title,
                labels={'month': 'Month', 'value': y_label, 'product': 'Product'},
                markers=True,
                template='plotly_white',
                color_discrete_sequence=COLORS,
            )
            fig.update_xaxes(tickangle=-45)
        else:
            x_label = grouping.replace('_', ' ').title()
            fig = px.line(
                df, x=grouping, y='value',
                title=title,
                labels={grouping: x_label, 'value': y_label},
                markers=True,
                template='plotly_white',
                color_discrete_sequence=COLORS,
            )

    elif chart_type == 'pie':
        name_col = grouping if grouping != 'month_product' else 'product'
        fig = px.pie(
            df, names=name_col, values='value',
            title=title,
            template='plotly_white',
            color_discrete_sequence=COLORS,
        )

    else:
        raise ValueError(f"Unknown chart_type: '{chart_type}'. Valid options: bar, line, pie.")

    fig.update_layout(
        title_font_size=14,
        title_font_color='#1a3a5c',
        margin=dict(t=55, b=40, l=50, r=20),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )

    return pio.to_html(
        fig,
        include_plotlyjs=include_plotlyjs,
        full_html=False,
        config={'displayModeBar': False},
    )


# ── HTML TEMPLATE ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f0f2f5;
    color: #333;
  }}
  .header {{
    background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%);
    color: white;
    padding: 28px 40px;
  }}
  .header h1 {{ font-size: 24px; margin-bottom: 6px; font-weight: 600; }}
  .header p  {{ opacity: .82; font-size: 14px; }}
  .filter-bar {{
    background: white;
    padding: 10px 40px;
    border-bottom: 1px solid #dde3ea;
    font-size: 13px;
    color: #666;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }}
  .filter-label {{ font-weight: 600; color: #444; }}
  .pill {{
    background: #e8f0fe;
    color: #2d6a9f;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
  }}
  .charts-area {{ padding: 28px 40px; }}
  .row {{
    display: flex;
    gap: 22px;
    margin-bottom: 22px;
    flex-wrap: wrap;
  }}
  .card {{
    background: white;
    border-radius: 10px;
    box-shadow: 0 1px 6px rgba(0,0,0,.08);
    flex: 1;
    min-width: 340px;
    overflow: hidden;
  }}
  .footer {{
    text-align: center;
    padding: 18px;
    color: #aaa;
    font-size: 12px;
    border-top: 1px solid #e8eaed;
    margin-top: 12px;
  }}
</style>
</head>
<body>

<div class="header">
  <h1>{title}</h1>
  <p>{description}</p>
</div>

<div class="filter-bar">
  <span class="filter-label">Filters applied:</span>
  {filter_pills}
</div>

<div class="charts-area">
{rows_html}
</div>

<div class="footer">
  Generated by Dashboard Agent &nbsp;&middot;&nbsp; {timestamp}
</div>

</body>
</html>"""


def build_filter_pills(filters: dict) -> str:
    return ' '.join(
        f'<span class="pill">{k.replace("_", " ").title()}: {v}</span>'
        for k, v in filters.items()
    )


def build_rows_html(charts_html: dict, layout: list) -> str:
    """Group charts into rows according to the layout spec."""
    rows: dict[int, list] = {}
    for entry in layout:
        rows.setdefault(entry['row'], []).append(entry)

    html_parts = []
    for row_num in sorted(rows.keys()):
        entries = sorted(rows[row_num], key=lambda x: x['col'])
        cards = '\n'.join(
            f'  <div class="card">{charts_html[e["chart_id"]]}</div>'
            for e in entries
        )
        html_parts.append(f'<div class="row">\n{cards}\n</div>')

    return '\n\n'.join(html_parts)


# ── MAIN ──────────────────────────────────────────────────────────────────────

def render(spec_path: str) -> str:
    """Read a spec JSON, build all charts, write HTML. Returns the output path."""
    with open(spec_path, encoding='utf-8') as f:
        spec = json.load(f)

    print(f"  Loading data files...")
    data = load_data()

    print(f"  Building {len(spec['charts'])} chart(s)...")
    charts_html: dict[str, str] = {}
    for idx, chart in enumerate(spec['charts']):
        df = compute_metric(data, chart)
        if df.empty:
            print(f"    ! '{chart['title']}' — no data for this time range, using placeholder")
        else:
            print(f"    OK  '{chart['title']}'  ({len(df)} data points)")
        include_js   = (idx == 0)   # embed plotly.js only once, in the first chart
        charts_html[chart['chart_id']] = create_chart_html(df, chart, include_js)

    html = HTML_TEMPLATE.format(
        title        = spec['title'],
        description  = spec['description'],
        filter_pills = build_filter_pills(spec.get('filters', {})),
        rows_html    = build_rows_html(charts_html, spec['layout']),
        timestamp    = datetime.now().strftime('%Y-%m-%d %H:%M'),
    )

    os.makedirs('output', exist_ok=True)
    spec_name   = os.path.splitext(os.path.basename(spec_path))[0]
    output_path = os.path.join('output', f'{spec_name}.html')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return output_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python renderer.py <path/to/spec.json>")
        sys.exit(1)

    spec_path = sys.argv[1]
    print(f"\nRendering: {spec_path}")
    output = render(spec_path)
    print(f"\n  Saved: {output}")
    print(f"  Open:  {os.path.abspath(output)}\n")
