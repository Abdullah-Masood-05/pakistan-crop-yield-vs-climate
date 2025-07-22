import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, Input, Output, State

# Load data
merged_df = pd.read_csv("merged_agri_climate_data.csv")
merged_df['Year'] = merged_df['Year'].astype(int)

# Dropdown options
provinces = sorted(merged_df['Province'].unique().tolist())
crops = sorted(merged_df['Crop'].unique().tolist())
years = sorted(int(y) for y in merged_df['Year'].unique())

# Initialize app
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server  
app.title = "Pakistan Agri-Climate Dashboard"

# Layout
app.layout = html.Div([
    dcc.Store(id='mobile-toggle-store', data={'showFilters': False}),
    dcc.Store(id='device-store'),

    # Top bar
    html.Div([
        html.Div("☰", className="menu-icon", id="menu-icon"),
        html.H2("Pakistan Crop Yield vs Climate", className="logo")
    ], className="top-bar"),

    # Filter section
    html.Div(
        id='filters-container',
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
                    marks={y: str(y) for y in years if y % 2 == 0},
                    id='year-slider'
                )
            ])
        ]
    ),

    # Graph rows
    html.Div(className='row', children=[
        html.Div(dcc.Graph(id='yield-trend'), className='graph-container'),
        html.Div(dcc.Graph(id='climate-trends'), className='graph-container')
    ]),
    html.Div(className='row', children=[
        html.Div(dcc.Graph(id='corr-heatmap'), className='graph-container'),
        html.Div(dcc.Graph(id='yield-bar'), className='graph-container')
    ]),
    html.Div(className='row', children=[
        html.Div(dcc.Graph(id='scatter-temp-yield'), className='graph-container'),
        html.Div(dcc.Graph(id='box-yield'), className='graph-container')
    ]),

    html.Footer("Data Source: Zenodo | Analysis by Abdullah Masood"),

    # Inject screen-width detection script
    html.Script('''
        document.addEventListener("DOMContentLoaded", function() {
            function updateDevice() {
                const width = window.innerWidth;
                const isMobile = width < 768;
                const store = window.dash_clientside;
                if (store && store.callback_context && store.callback_context.clientside) {
                    DashStore.dispatch({
                        id: 'device-store',
                        props: { data: { isMobile: isMobile } }
                    });
                }
            }
            window.addEventListener("resize", updateDevice);
            updateDevice();
        });
    ''')
])

# Toggle filter menu
@app.callback(
    Output('filters-container', 'className'),
    Input('menu-icon', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_filters(n_clicks):
    if n_clicks and n_clicks % 2 == 1:
        return 'filters show'
    return 'filters'


# Update all graphs
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
        Input('year-slider', 'value'),
        Input('device-store', 'data')
    ]
)
def update_charts(province, crop, year, device_data):
    is_mobile = device_data.get('isMobile') if device_data else False
    short_crop = crop if not is_mobile else crop[:3]
    short_prov = province if not is_mobile else province[:3]
    font_size = 10 if is_mobile else 12
    title_font = 13 if is_mobile else 18

    df = merged_df[(merged_df['Province'] == province) & (merged_df['Crop'] == crop)]
    df_year = df[df['Year'] <= year]
    latest = df[df['Year'] == year]
    climate_cols = ['temperature_2m_mean', 'precipitation_sum', 'fao_evapotranspiration']

    # 1. Yield Trend
    fig_yield = px.line(df_year, x='Year', y='Yield',
                        title=f'{short_crop} Yield Trend ({short_prov})', markers=True)
    fig_yield.update_traces(line=dict(width=3, color='darkgreen'))
    fig_yield.update_layout(
        height=350, title_x=0.5, font_size=font_size,
        title_font_size=title_font,
        xaxis=dict(tickangle=-45, tickfont=dict(size=font_size)),
        yaxis=dict(title="Yield (tons/ha)", tickfont=dict(size=font_size))
    )

    # 2. Climate Trends
    mpg = df_year.melt(id_vars=['Year'], value_vars=climate_cols, var_name='Metric', value_name='Value')
    mpg['Metric'] = mpg['Metric'].replace({
        'temperature_2m_mean': 'Temp (°C)',
        'precipitation_sum': 'Precip (mm)',
        'fao_evapotranspiration': 'ET (mm)'
    })
    fig_climate = px.line(mpg, x='Year', y='Value', color='Metric',
                          title=f'Climate Trend ({short_prov}, {short_crop})')
    fig_climate.update_layout(
        height=350, title_x=0.5, font_size=font_size,
        title_font_size=title_font,
        xaxis=dict(tickangle=-45, tickfont=dict(size=font_size)),
        yaxis=dict(tickfont=dict(size=font_size))
    )

    # 3. Correlation Heatmap
    corr = latest[['Yield'] + climate_cols].corr()
    fig_corr = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns, y=corr.index,
        colorscale='YlGnBu', zmin=-1, zmax=1, hoverongaps=False
    ))
    fig_corr.update_layout(
        title=f'Corr Matrix ({short_prov}, {year})',
        height=350, title_x=0.5,
        font_size=font_size, title_font_size=title_font
    )

    # 4. Yield by Province
    comp = merged_df[(merged_df['Year'] == year) & (merged_df['Crop'] == crop)]
    fig_bar = px.bar(comp, x='Province', y='Yield',
                     title=f'Yield by Province ({year})',
                     color='Yield', color_continuous_scale='Viridis')
    fig_bar.update_layout(
        height=350, title_x=0.5,
        font_size=font_size, title_font_size=title_font
    )

    # 5. Temp vs Yield
    fig_scatter = px.scatter(latest, x='temperature_2m_mean', y='Yield',
                             size='precipitation_sum', trendline='ols',
                             title=f'Temp vs Yield ({short_prov}, {year})',
                             labels={'temperature_2m_mean': 'Temp (°C)', 'Yield': 'Yield (tons/ha)'})
    fig_scatter.update_layout(
        height=350, title_x=0.5,
        xaxis=dict(tickfont=dict(size=font_size)),
        yaxis=dict(tickfont=dict(size=font_size)),
        font_size=font_size, title_font_size=title_font
    )

    # 6. Yield Box Plot
    fig_box = px.box(df, x='Province', y='Yield',
                     title=f'Yield Dist. up to {year}', color='Province')
    fig_box.update_layout(
        height=350, title_x=0.5,
        font_size=font_size, title_font_size=title_font
    )

    return fig_yield, fig_climate, fig_corr, fig_bar, fig_scatter, fig_box


if __name__ == '__main__':
    app.run(debug=False)
