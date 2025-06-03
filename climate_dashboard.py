"""Pakistan Crop Yield vs Climate — interactive analytics dashboard.

A Dash application exploring how climate variables (temperature,
precipitation, evapotranspiration) relate to crop yields across the
provinces of Pakistan, 2001-2022.

The source dataset is monthly; every analytical view aggregates it to
annual values first (mean temperature, total precipitation, total
evapotranspiration) so that trends and correlations are computed on
one observation per year.

Run locally:      python climate_dashboard.py
Run in prod:      gunicorn climate_dashboard:server
"""

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from dash import Input, Output, dcc, html
from plotly.subplots import make_subplots

# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #

COLORS = {
    "surface": "#fcfcfb",
    "ink": "#0b0b0b",
    "ink_secondary": "#52514e",
    "ink_muted": "#898781",
    "grid": "#e1e0d9",
    "baseline": "#c3c2b7",
    # Series colors follow the entity, everywhere in the app:
    "yield": "#008300",
    "temp": "#e34948",
    "precip": "#2a78d6",
    "et": "#eda100",
    "bar_muted": "#dcdbd3",
    "delta_up": "#006300",
    "delta_down": "#d03b3b",
}

FONT_STACK = 'system-ui, -apple-system, "Segoe UI", sans-serif'

pio.templates["agri_light"] = go.layout.Template(
    layout=go.Layout(
        font=dict(family=FONT_STACK, size=12, color=COLORS["ink_secondary"]),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=56, r=20, t=24, b=44),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor=COLORS["baseline"],
            ticks="outside",
            tickcolor=COLORS["baseline"],
            ticklen=4,
            zeroline=False,
            title_font=dict(size=12, color=COLORS["ink_muted"]),
        ),
        yaxis=dict(
            gridcolor=COLORS["grid"],
            gridwidth=1,
            showline=False,
            zeroline=False,
            title_font=dict(size=12, color=COLORS["ink_muted"]),
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=COLORS["grid"],
            font=dict(family=FONT_STACK, size=12, color=COLORS["ink"]),
        ),
        colorway=[COLORS["yield"], COLORS["precip"], COLORS["temp"], COLORS["et"]],
    )
)
pio.templates.default = "agri_light"

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}
CHART_HEIGHT = 330

REPO_URL = "https://github.com/Abdullah-Masood-05/pakistan-crop-yield-vs-climate"
DATA_URL = "https://zenodo.org/records/15486470"

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

CLIMATE_LABELS = {
    "temperature_2m_mean": "Temp",
    "precipitation_sum": "Precip",
    "fao_evapotranspiration": "ET",
}


def load_annual_data(path: str = "merged_agri_climate_data.csv") -> pd.DataFrame:
    """Collapse the monthly source data to one row per year/province/crop."""
    monthly = pd.read_csv(path)
    monthly["Year"] = monthly["Year"].astype(int)
    return monthly.groupby(["Year", "Province", "Crop"], as_index=False).agg(
        Yield=("Yield", "first"),
        temperature_2m_mean=("temperature_2m_mean", "mean"),
        precipitation_sum=("precipitation_sum", "sum"),
        fao_evapotranspiration=("fao_evapotranspiration", "sum"),
    )


annual_df = load_annual_data()

PROVINCES = sorted(annual_df["Province"].unique())
CROPS = sorted(annual_df["Crop"].unique())
YEARS = sorted(int(y) for y in annual_df["Year"].unique())
DEFAULT_CROP = "wheat" if "wheat" in CROPS else CROPS[0]

# --------------------------------------------------------------------------- #
# Figures
# --------------------------------------------------------------------------- #


def message_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=CHART_HEIGHT,
        xaxis_visible=False,
        yaxis_visible=False,
        annotations=[
            dict(
                text=message,
                showarrow=False,
                font=dict(size=13, color=COLORS["ink_muted"]),
            )
        ],
    )
    return fig


def yield_trend_figure(history: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Scatter(
            x=history["Year"],
            y=history["Yield"],
            mode="lines+markers",
            line=dict(color=COLORS["yield"], width=2, shape="spline", smoothing=0.6),
            marker=dict(
                size=8,
                color=COLORS["yield"],
                line=dict(color=COLORS["surface"], width=2),
            ),
            hovertemplate="%{x} — %{y:.1f} t/ha<extra></extra>",
        )
    )
    fig.update_layout(
        height=CHART_HEIGHT,
        hovermode="x unified",
        yaxis_title="Yield (t/ha)",
        xaxis=dict(dtick=3),
    )
    return fig


def climate_trend_figure(history: pd.DataFrame) -> go.Figure:
    metrics = [
        ("temperature_2m_mean", "Mean temperature (°C)", COLORS["temp"]),
        ("precipitation_sum", "Total precipitation (mm)", COLORS["precip"]),
        ("fao_evapotranspiration", "Evapotranspiration (mm)", COLORS["et"]),
    ]
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.22,
        subplot_titles=[label for _, label, _ in metrics],
    )
    for row, (column, label, color) in enumerate(metrics, start=1):
        fig.add_trace(
            go.Scatter(
                x=history["Year"],
                y=history[column],
                mode="lines",
                line=dict(color=color, width=2),
                name=label,
                hovertemplate="%{y:.1f}<extra>" + label + "</extra>",
            ),
            row=row,
            col=1,
        )
    fig.update_annotations(
        x=0, xanchor="left", yshift=4, font=dict(size=11, color=COLORS["ink_muted"])
    )
    fig.update_layout(
        height=CHART_HEIGHT,
        showlegend=False,
        hovermode="x unified",
        margin=dict(l=56, r=20, t=32, b=36),
    )
    fig.update_xaxes(dtick=6)
    return fig


def correlation_figure(history: pd.DataFrame) -> go.Figure:
    if len(history) < 3:
        return message_figure("Select a later year — at least three seasons are needed.")
    frame = history[["Yield", *CLIMATE_LABELS]].rename(columns=CLIMATE_LABELS)
    corr = frame.corr().round(2)
    fig = px.imshow(
        corr,
        text_auto=".2f",
        zmin=-1,
        zmax=1,
        color_continuous_scale="RdBu_r",
        aspect="auto",
    )
    fig.update_traces(hovertemplate="%{x} × %{y}: %{z:.2f}<extra></extra>")
    fig.update_layout(
        height=CHART_HEIGHT,
        margin=dict(l=56, r=20, t=16, b=36),
        coloraxis_colorbar=dict(
            thickness=10, outlinewidth=0, tickfont=dict(size=11), title=""
        ),
    )
    fig.update_xaxes(showgrid=False, showline=False, ticks="")
    fig.update_yaxes(showgrid=False, showline=False, ticks="")
    return fig


def province_bar_figure(comparison: pd.DataFrame, selected_province: str) -> go.Figure:
    comparison = comparison.sort_values("Yield", ascending=True)
    colors = [
        COLORS["yield"] if p == selected_province else COLORS["bar_muted"]
        for p in comparison["Province"]
    ]
    fig = go.Figure(
        go.Bar(
            x=comparison["Yield"],
            y=comparison["Province"],
            orientation="h",
            width=0.45,
            marker=dict(color=colors, line_width=0),
            text=[f"{v:,.1f}" for v in comparison["Yield"]],
            textposition="outside",
            textfont=dict(size=12, color=COLORS["ink_secondary"]),
            cliponaxis=False,
            hovertemplate="%{y}: %{x:.1f} t/ha<extra></extra>",
        )
    )
    fig.update_layout(
        height=CHART_HEIGHT,
        barcornerradius=4,
        xaxis=dict(title="Yield (t/ha)", showgrid=True, gridcolor=COLORS["grid"]),
        yaxis=dict(showgrid=False),
        margin=dict(l=90, r=48, t=24, b=44),
    )
    return fig


def temp_yield_figure(history: pd.DataFrame) -> go.Figure:
    trendline = "ols" if len(history) >= 3 else None
    fig = px.scatter(
        history,
        x="temperature_2m_mean",
        y="Yield",
        trendline=trendline,
        trendline_color_override=COLORS["ink_muted"],
        custom_data=["Year"],
    )
    fig.update_traces(
        selector=dict(mode="markers"),
        marker=dict(
            size=10,
            color=COLORS["yield"],
            line=dict(color=COLORS["surface"], width=2),
        ),
        hovertemplate=(
            "%{customdata[0]} — %{x:.1f} °C, %{y:.1f} t/ha<extra></extra>"
        ),
    )
    fig.update_traces(selector=dict(mode="lines"), line=dict(width=2))
    fig.update_layout(
        height=CHART_HEIGHT,
        xaxis_title="Annual mean temperature (°C)",
        yaxis_title="Yield (t/ha)",
    )
    return fig


def distribution_figure(crop_history: pd.DataFrame) -> go.Figure:
    fig = go.Figure(
        go.Box(
            x=crop_history["Province"],
            y=crop_history["Yield"],
            marker=dict(color=COLORS["yield"], size=4),
            line=dict(color=COLORS["yield"], width=2),
            fillcolor="rgba(0, 131, 0, 0.08)",
            boxmean=True,
            hovertemplate="%{x}: %{y:.1f} t/ha<extra></extra>",
        )
    )
    fig.update_layout(height=CHART_HEIGHT, yaxis_title="Yield (t/ha)", showlegend=False)
    return fig


# --------------------------------------------------------------------------- #
# Layout helpers
# --------------------------------------------------------------------------- #


def kpi_tile(label, value, unit, delta_text=None, direction="neutral"):
    arrow = {"up": "▲", "down": "▼"}.get(direction, "")
    children = [
        html.Span(label, className="kpi-label"),
        html.Div(
            [
                html.Span(value, className="kpi-value"),
                html.Span(unit, className="kpi-unit"),
            ],
            className="kpi-figure",
        ),
    ]
    if delta_text:
        children.append(
            html.Span(f"{arrow} {delta_text}".strip(), className=f"kpi-delta {direction}")
        )
    return html.Div(children, className="card kpi-tile")


def chart_card(graph_id, title, subtitle):
    return html.Div(
        className="card chart-card",
        children=[
            html.Div(
                className="chart-card-head",
                children=[html.H3(title), html.P(subtitle)],
            ),
            dcc.Graph(
                id=graph_id,
                config=GRAPH_CONFIG,
                className="chart-card-plot",
                style={"height": f"{CHART_HEIGHT}px"},
            ),
        ],
    )


def build_layout() -> html.Div:
    return html.Div(
        className="app",
        children=[
            html.Header(
                className="top-bar",
                children=[
                    html.Div(
                        className="brand",
                        children=[
                            html.Img(src="/assets/logo.svg", className="brand-mark", alt=""),
                            html.Div(
                                [
                                    html.H1("Pakistan Crop Yield × Climate"),
                                    html.P(
                                        "Provincial crop performance against two decades "
                                        "of climate data · 2001–2022"
                                    ),
                                ]
                            ),
                        ],
                    ),
                    html.A(
                        "View source ↗",
                        href=REPO_URL,
                        target="_blank",
                        rel="noopener",
                        className="source-link",
                    ),
                ],
            ),
            html.Main(
                [
                    html.Section(
                        className="card filters",
                        children=[
                            html.Div(
                                className="filter",
                                children=[
                                    html.Label("Province", htmlFor="province-dropdown"),
                                    dcc.Dropdown(
                                        id="province-dropdown",
                                        options=PROVINCES,
                                        value=PROVINCES[0],
                                        clearable=False,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="filter",
                                children=[
                                    html.Label("Crop", htmlFor="crop-dropdown"),
                                    dcc.Dropdown(
                                        id="crop-dropdown",
                                        options=[
                                            {"label": c.title(), "value": c} for c in CROPS
                                        ],
                                        value=DEFAULT_CROP,
                                        clearable=False,
                                    ),
                                ],
                            ),
                            html.Div(
                                className="filter filter-year",
                                children=[
                                    html.Label("Year"),
                                    dcc.Slider(
                                        id="year-slider",
                                        min=YEARS[0],
                                        max=YEARS[-1],
                                        step=1,
                                        value=YEARS[-1],
                                        marks={
                                            y: str(y)
                                            for y in YEARS
                                            if y % 3 == 0 or y in (YEARS[0], YEARS[-1])
                                        },
                                        tooltip={
                                            "placement": "bottom",
                                            "always_visible": False,
                                        },
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Section(id="kpi-row", className="kpi-row"),
                    html.Section(
                        className="chart-grid",
                        children=[
                            chart_card(
                                "yield-trend",
                                "Yield trend",
                                "Annual yield for the selected crop and province",
                            ),
                            chart_card(
                                "climate-trends",
                                "Climate trends",
                                "Annual temperature, precipitation and evapotranspiration",
                            ),
                            chart_card(
                                "corr-heatmap",
                                "Yield–climate correlation",
                                "Pearson correlation across the selected seasons",
                            ),
                            chart_card(
                                "yield-bar",
                                "Provincial comparison",
                                "Yield by province in the selected year",
                            ),
                            chart_card(
                                "scatter-temp-yield",
                                "Temperature vs yield",
                                "One point per season, with an OLS trend line",
                            ),
                            chart_card(
                                "box-yield",
                                "Yield distribution",
                                "Spread of annual yields by province",
                            ),
                        ],
                    ),
                ]
            ),
            html.Footer(
                [
                    html.Span("Data: "),
                    html.A(
                        "Climate & Agriculture in Pakistan — Zenodo",
                        href=DATA_URL,
                        target="_blank",
                        rel="noopener",
                    ),
                    html.Span(" · Built with Dash & Plotly · Analysis by "),
                    html.A(
                        "Abdullah Masood",
                        href="https://github.com/Abdullah-Masood-05",
                        target="_blank",
                        rel="noopener",
                    ),
                ]
            ),
        ],
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = dash.Dash(
    __name__,
    title="Pakistan Crop Yield × Climate",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server
app.layout = build_layout()


@app.callback(
    Output("kpi-row", "children"),
    Output("yield-trend", "figure"),
    Output("climate-trends", "figure"),
    Output("corr-heatmap", "figure"),
    Output("yield-bar", "figure"),
    Output("scatter-temp-yield", "figure"),
    Output("box-yield", "figure"),
    Input("province-dropdown", "value"),
    Input("crop-dropdown", "value"),
    Input("year-slider", "value"),
)
def update_dashboard(province, crop, year):
    selection = annual_df[
        (annual_df["Province"] == province) & (annual_df["Crop"] == crop)
    ].sort_values("Year")
    history = selection[selection["Year"] <= year]
    comparison = annual_df[(annual_df["Year"] == year) & (annual_df["Crop"] == crop)]
    crop_history = annual_df[
        (annual_df["Crop"] == crop) & (annual_df["Year"] <= year)
    ]

    return (
        build_kpis(selection, year),
        yield_trend_figure(history),
        climate_trend_figure(history),
        correlation_figure(history),
        province_bar_figure(comparison, province),
        temp_yield_figure(history),
        distribution_figure(crop_history),
    )


def build_kpis(selection: pd.DataFrame, year: int) -> list:
    current = selection[selection["Year"] == year]
    previous = selection[selection["Year"] == year - 1]
    if current.empty:
        return [kpi_tile("No data", "–", "") for _ in range(4)]

    row = current.iloc[0]
    tiles = []

    yield_delta, yield_dir = None, "neutral"
    if not previous.empty:
        change = row["Yield"] - previous.iloc[0]["Yield"]
        yield_dir = "up" if change >= 0 else "down"
        yield_delta = f"{abs(change):.1f} t/ha vs {year - 1}"
    tiles.append(
        kpi_tile(f"Yield · {year}", f"{row['Yield']:,.1f}", "t/ha", yield_delta, yield_dir)
    )

    for column, label, unit, fmt in [
        ("temperature_2m_mean", "Mean temperature", "°C", "{:.1f}"),
        ("precipitation_sum", "Total precipitation", "mm", "{:,.0f}"),
    ]:
        delta_text, direction = None, "neutral"
        if not previous.empty:
            change = row[column] - previous.iloc[0][column]
            direction = "neutral"
            arrow_dir = "up" if change >= 0 else "down"
            delta_text = f"{fmt.format(abs(change))} {unit} vs {year - 1}"
            delta_text = ("▲ " if arrow_dir == "up" else "▼ ") + delta_text
        tiles.append(kpi_tile(label, fmt.format(row[column]), unit, delta_text, direction))

    peak = selection.loc[selection["Yield"].idxmax()]
    tiles.append(
        kpi_tile(
            "Record yield · 2001–2022",
            f"{peak['Yield']:,.1f}",
            "t/ha",
            f"set in {int(peak['Year'])}",
        )
    )
    return tiles


if __name__ == "__main__":
    app.run(debug=False)
