import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output

# Load merged data
merged_df = pd.read_csv("merged_agri_climate_data.csv")
merged_df['Year'] = merged_df['Year'].astype(int)

# Initialize Dash app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "Pakistan Agri-Climate Dashboard"

# Dropdown options
provinces = sorted(merged_df['Province'].unique().tolist())
crops = sorted(merged_df['Crop'].unique().tolist())
years = sorted(int(y) for y in merged_df['Year'].unique())

# Layout
app.layout = html.Div(
    children=[
        html.H1("🌾 Pakistan Agriculture & Climate Dashboard"),
        html.P(
            "Interactive visualization of crop yield trends and climate impacts across Pakistan's provinces."
        ),

        # Filters
        html.Div(
            className='filters',
            children=[
                html.Div([
                    html.Label("Province:"),
                    dcc.Dropdown(provinces, provinces[0], id='province-dropdown')
                ]),

                html.Div([
                    html.Label("Crop:"),
                    dcc.Dropdown(crops, crops[-2], id='crop-dropdown')
                ]),

                html.Div([
                    html.Label("Year:"),
                    dcc.Slider(
                        min=years[0],
                        max=years[-1],
                        step=1,
                        value=years[-1],
                        marks={y: str(y) for y in years if y % 2 == 0},  # Every 2 years
                        id='year-slider'
                    )
                ])
            ]
        ),

        # Graph containers
        html.Div(
            className='row',
            children=[
                html.Div(dcc.Graph(id='yield-trend'), className='graph-container'),
                html.Div(dcc.Graph(id='climate-trends'), className='graph-container')
            ]
        ),

        html.Div(
            className='row',
            children=[
                html.Div(dcc.Graph(id='corr-heatmap'), className='graph-container'),
                html.Div(dcc.Graph(id='yield-bar'), className='graph-container')
            ]
        ),

        html.Div(
            className='row',
            children=[
                html.Div(dcc.Graph(id='scatter-temp-yield'), className='graph-container'),
                html.Div(dcc.Graph(id='box-yield'), className='graph-container')
            ]
        ),

        html.Footer(
            "Data Source: Zenodo (Crops & Climate), Analysis by Gojo"
        )
    ]
)

# Callbacks
@app.callback(
    [
        Output('yield-trend', 'figure'),
        Output('climate-trends', 'figure'),
        Output('corr-heatmap', 'figure'),
        Output('yield-bar', 'figure'),
        Output('scatter-temp-yield', 'figure'),
        Output('box-yield', 'figure')
    ],
    [
        Input('province-dropdown', 'value'),
        Input('crop-dropdown', 'value'),
        Input('year-slider', 'value')
    ]
)
def update_charts(province, crop, year):
    df = merged_df[(merged_df['Province'] == province) & (merged_df['Crop'] == crop)]
    df_year = df[df['Year'] <= year]
    latest = df[df['Year'] == year]

    # 1. Yield Trend Over Time
    fig_yield = px.line(
        df_year, x='Year', y='Yield',
        title=f'{crop} Yield Trend ({province})', markers=True
    )
    fig_yield.update_traces(line=dict(width=3, color='darkgreen'))
    fig_yield.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        hovermode='closest',
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(title="Yield (tons/ha)", tickfont=dict(size=10))
    )

    # 2. Climate Trends
    climate_cols = ['temperature_2m_mean', 'precipitation_sum', 'fao_evapotranspiration']
    mpg = df_year.melt(id_vars=['Year'], value_vars=climate_cols, var_name='Metric', value_name='Value')
    mpg['Metric'] = mpg['Metric'].replace({
        'temperature_2m_mean': 'Temp (°C)',
        'precipitation_sum': 'Precip (mm)',
        'fao_evapotranspiration': 'ET (mm)'
    })
    fig_climate = px.line(
        mpg, x='Year', y='Value', color='Metric',
        title=f'Climate Metrics Trend ({province}, {crop})'
    )
    fig_climate.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        hovermode='closest',
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10))
    )

    # 3. Correlation Heatmap
    sub = latest[['Yield'] + climate_cols].corr()
    fig_corr = go.Figure(
        go.Heatmap(
            z=sub.values, x=sub.columns, y=sub.index,
            colorscale='YlGnBu', zmin=-1, zmax=1,
            hoverongaps=False
        )
    )
    fig_corr.update_layout(
        title=f'Correlation Matrix ({province}, {year})',
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        font=dict(size=10)
    )

    # 4. Yield Comparison Bar Chart
    comp = merged_df[(merged_df['Year'] == year) & (merged_df['Crop'] == crop)]
    fig_bar = px.bar(
        comp, x='Province', y='Yield',
        title=f'Yield by Province in {year}',
        color='Yield', color_continuous_scale='Viridis'
    )
    fig_bar.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        font=dict(size=10)
    )

    # 5. Scatter: Temp vs Yield
    fig_scatter = px.scatter(
        latest, x='temperature_2m_mean', y='Yield',
        size='precipitation_sum',
        title=f'Temp vs Yield ({province}, {year})',
        trendline='ols',
        labels={
            'temperature_2m_mean': 'Temp (°C)',
            'Yield': 'Yield (tons/ha)',
            'precipitation_sum': 'Precip (mm)'
        }
    )
    fig_scatter.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        xaxis=dict(tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=10))
    )

    # 6. Yield Distribution Box Plot
    fig_box = px.box(
        df, x='Province', y='Yield',
        title=f'Yield Distribution up to {year}', color='Province',
        labels={'Yield': 'Yield (tons/ha)'}
    )
    fig_box.update_layout(
        autosize=True,
        margin=dict(l=40, r=40, t=50, b=40),
        height=350,
        title_x=0.5,
        font=dict(size=10)
    )

    return fig_yield, fig_climate, fig_corr, fig_bar, fig_scatter, fig_box


if __name__ == '__main__':
    app.run(debug=False)
