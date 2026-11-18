import argparse
from pathlib import Path
from textwrap import wrap

from dash import Dash, Input, Output, State, ctx, dcc, html, no_update
import dash_ag_grid as dag
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard_data import (
    BANDS, LABELS, collection_summary, correlation_summary, export_frame,
    filter_libraries, load_data,
)

LIBRARIES, DATASET = load_data()
TEAL = '#17695b'
INK = '#203b36'
MUTED = '#73827c'
GOLD = '#d5a34a'
COLORS = [[0, '#d3e6d8'], [0.35, '#89baa3'], [0.7, '#398b77'], [1, '#124c43']]
GRAPH_CONFIG = {'displaylogo': False, 'responsive': True, 'scrollZoom': False,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'autoScale2d'],
                'toImageButtonOptions': {'format': 'png', 'scale': 2}}


def number(value, decimals=0):
    return '—' if pd.isna(value) else f'{value:,.{decimals}f}'


def figure_base(fig, height=340):
    fig.update_layout(
        template='plotly_white', height=height, paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)', font={'family': 'Arial, sans-serif', 'color': INK, 'size': 12},
        margin={'l': 58, 'r': 24, 't': 16, 'b': 48},
        hoverlabel={'bgcolor': '#fff', 'font_color': INK},
    )
    fig.update_xaxes(gridcolor='#edf0eb', zeroline=False, title_font_size=12)
    fig.update_yaxes(gridcolor='#edf0eb', zeroline=False, title_font_size=12)
    return fig


def empty_figure(message, height=340):
    fig = figure_base(go.Figure(), height)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.add_annotation(text=message, x=.5, y=.5, xref='paper', yref='paper',
                       showarrow=False, font={'color': MUTED, 'size': 13})
    return fig


def map_figure(frame, color, extent, basemap):
    mapped = frame[frame.mappable]
    if extent == 'mainland':
        mapped = mapped[mapped.mainland]
    if mapped.empty:
        return empty_figure('No mapped libraries in this view.<br>Try “All territories” or broaden your filters.', 430), '0 libraries plotted'
    fig = go.Figure()
    known = mapped[mapped[color].notna()]
    missing = mapped[mapped[color].isna()]
    if len(missing):
        fig.add_trace(go.Scattermap(
            lat=missing.latitude, lon=missing.longitude, mode='markers', name='Not reported',
            marker={'color': '#aeb7b2', 'size': 7, 'opacity': .65},
            customdata=missing[['id', 'name', 'city']].values,
            hovertemplate='<b>%{customdata[1]}</b><br>%{customdata[2]}<br>Not reported<extra></extra>',
        ))
    if len(known):
        is_count = color in ['books', 'loans', 'visits', 'borrowers']
        values = np.log10(known[color] + 1) if is_count else known[color]
        whole = LIBRARIES[color].dropna()
        cmax = np.log10(whole.max() + 1) if is_count else whole.max()
        colorbar = {'title': {'text': LABELS[color], 'font': {'size': 11}},
                    'thickness': 9, 'len': .6, 'x': 1.01, 'outlinewidth': 0}
        if is_count:
            colorbar.update(tickvals=[0, 2, 3, 4, 5, 6], ticktext=['0', '100', '1k', '10k', '100k', '1m'])
        fig.add_trace(go.Scattermap(
            lat=known.latitude, lon=known.longitude, mode='markers', name=LABELS[color],
            marker={'color': values, 'size': 7, 'opacity': .8, 'colorscale': COLORS,
                    'cmin': 0, 'cmax': max(float(cmax), 1), 'colorbar': colorbar},
            customdata=known[['id', 'name', 'city', color]].values,
            hovertemplate='<b>%{customdata[1]}</b><br>%{customdata[2]}<br>' + LABELS[color] + ': %{customdata[3]:,.0f}<extra></extra>',
        ))
    lat_span = float(mapped.latitude.max() - mapped.latitude.min())
    lon_span = float(mapped.longitude.max() - mapped.longitude.min())
    span = max(lat_span * 1.8, lon_span, .15)
    zoom = float(np.clip(np.log2(300 / span), 1, 10))
    center = {'lat': float((mapped.latitude.min() + mapped.latitude.max()) / 2),
              'lon': float((mapped.longitude.min() + mapped.longitude.max()) / 2)}
    fig.update_layout(
        height=430, margin={'l': 0, 'r': 30, 't': 0, 'b': 0}, showlegend=False,
        map={'style': 'carto-positron' if basemap == 'streets' else 'white-bg', 'center': center, 'zoom': zoom},
        paper_bgcolor='#f7f8f4', font={'family': 'Arial', 'color': INK},
        uirevision=f'{extent}-{basemap}-' + str(tuple(frame.id)),
        hoverlabel={'bgcolor': '#fff', 'font_color': INK},
    )
    excluded = len(frame) - len(mapped)
    note = f'{len(mapped):,} libraries plotted'
    if excluded:
        note += f' · {excluded:,} outside this view or without coordinates'
    if len(missing):
        note += f' · {len(missing):,} grey markers: value not reported'
    return fig, note


def band_figure(frame, metric):
    summary = collection_summary(frame, metric)
    available = summary[summary['count'] > 0]
    if available.empty:
        return empty_figure('No reported activity and collection pairs.', 310)
    fig = go.Figure(go.Bar(
        x=summary['median'], y=BANDS, orientation='h',
        marker={'color': ['#d8e7de', '#bdd7c8', '#94bda9', '#6b9e89', '#397a65', TEAL],
                'cornerradius': 4},
        customdata=summary[['count']].values,
        hovertemplate='%{y} books<br>Median ' + metric + ': %{x:,.0f}<br>%{customdata[0]:,} reporting libraries<extra></extra>',
        text=[number(v) if n else 'No data' for v, n in zip(summary['median'], summary['count'])],
        textposition='outside', cliponaxis=False,
    ))
    figure_base(fig, 310)
    fig.update_layout(margin={'l': 76, 'r': 68, 't': 10, 'b': 46}, bargap=.4)
    fig.update_yaxes(autorange='reversed', showgrid=False, title=None)
    fig.update_xaxes(title=f'Median {metric}', rangemode='tozero')
    return fig


def scatter_figure(frame, x, metric, scale):
    pairs = frame.dropna(subset=[x, metric])
    zero_count = 0
    if scale == 'log':
        positive = pairs[x].gt(0) & pairs[metric].gt(0)
        zero_count = int((~positive).sum())
        pairs = pairs[positive]
    note = f'{len(pairs):,} libraries with both measures · {len(frame) - len(pairs) - zero_count:,} missing pairs'
    if scale == 'log':
        note += f' · {zero_count:,} zero-value pairs omitted on log axes'
    if pairs.empty:
        return empty_figure('No comparable values.<br>Change the measures, scale, or filters.', 350), note
    fig = go.Figure(go.Scattergl(
        x=pairs[x], y=pairs[metric], mode='markers',
        marker={'size': 6, 'color': TEAL, 'opacity': .48, 'line': {'width': 0}},
        customdata=pairs[['id', 'name', 'city']].values,
        hovertemplate='<b>%{customdata[1]}</b><br>%{customdata[2]}<br>' + LABELS[x]
                      + ': %{x:,.0f}<br>' + LABELS[metric] + ': %{y:,.0f}<extra></extra>',
    ))
    figure_base(fig, 350)
    fig.update_xaxes(type=scale, title=LABELS[x])
    fig.update_yaxes(type=scale, title=LABELS[metric])
    if scale == 'log':
        fig.update_xaxes(dtick=1)
        fig.update_yaxes(dtick=1)
    return fig, note


def heatmap_figure(frame):
    columns = ['books', 'loans', 'borrowers', 'visits', 'population', 'income', 'rent']
    labels = ['Books', 'Loans', 'Borrowers', 'Visits', 'Population', 'Income', 'Rent']
    correlation, counts = correlation_summary(frame, columns)
    if correlation.isna().all().all():
        return empty_figure('At least 10 paired observations are needed.<br>Broaden the filters to compare measures.', 350)
    fig = go.Figure(go.Heatmap(
        z=correlation.values, x=labels, y=labels, zmin=-1, zmax=1,
        colorscale=[[0, '#c78c67'], [.5, '#f4f3ec'], [1, TEAL]],
        customdata=counts.values, text=correlation.round(2).values,
        texttemplate='%{text:.2f}', textfont={'size': 11},
        xgap=3, ygap=3, hoverongaps=False,
        hovertemplate='%{y} × %{x}<br>Spearman ρ = %{z:.2f}<br>%{customdata:,} paired libraries<extra></extra>',
        colorbar={'thickness': 8, 'len': .75, 'tickvals': [-1, 0, 1], 'outlinewidth': 0},
    ))
    figure_base(fig, 350)
    fig.update_layout(margin={'l': 78, 'r': 24, 't': 12, 'b': 58})
    fig.update_yaxes(autorange='reversed', showgrid=False)
    fig.update_xaxes(showgrid=False)
    return fig


def regional_figure(frame, metric):
    area = 'department' if frame.region.nunique() == 1 else 'region'
    areas = (frame.loc[frame[area].ne('Unknown')].groupby(area)[metric]
             .agg(count='count', median='median', lower=lambda values: values.quantile(.25),
                  upper=lambda values: values.quantile(.75)))
    eligible = areas[areas['count'] >= 5]
    selected = eligible.sort_values(['count', 'median'], ascending=False).head(8).sort_values('median')
    note = f'{len(selected)} of {len(eligible)} {area}s with at least 5 reporting libraries'
    if len(eligible) > 8:
        note += ' · Showing the 8 largest reporting samples'
    if selected.empty:
        return empty_figure('Not enough reported activity per area.<br>Broaden your filters to compare places.', 360), note
    labels = ['<br>'.join(wrap(name, 20, break_long_words=False, break_on_hyphens=False)) for name in selected.index]
    fig = go.Figure(go.Scatter(
        x=selected['median'], y=labels, mode='markers',
        marker={'color': TEAL, 'size': 9, 'line': {'color': '#fff', 'width': 1}},
        error_x={'type': 'data', 'symmetric': False,
                 'array': selected['upper'] - selected['median'],
                 'arrayminus': selected['median'] - selected['lower'],
                 'color': '#9bbca9', 'thickness': 3, 'width': 5},
        customdata=np.column_stack([selected.index, selected['count'], selected['lower'], selected['upper']]),
        hovertemplate='<b>%{customdata[0]}</b><br>Median ' + metric
                      + ': %{x:,.0f}<br>Middle 50%: %{customdata[2]:,.0f}–%{customdata[3]:,.0f}'
                      + '<br>%{customdata[1]:,} reporting libraries<extra></extra>',
    ))
    figure_base(fig, 360)
    fig.update_layout(margin={'l': 150, 'r': 22, 't': 15, 'b': 48})
    fig.update_xaxes(title=LABELS[metric] + ' per library', rangemode='tozero')
    fig.update_yaxes(showgrid=False, tickfont_size=10)
    return fig, note


def coverage_figure(frame):
    if frame.empty:
        return empty_figure('No libraries selected.<br>Broaden the filters to inspect reporting coverage.', 360)
    columns = ['books', 'loans', 'borrowers', 'visits', 'seats', 'population', 'income', 'rent']
    labels = ['Books', 'Loans', 'Borrowers', 'Visits', 'Seats', 'Population', 'Income', 'Rent']
    counts = frame[columns].notna().sum().to_numpy()
    available = counts / len(frame) * 100
    fig = go.Figure()
    for name, values, totals, color in [
        ('Available', available, counts, TEAL),
        ('Missing / unmatched', 100 - available, len(frame) - counts, '#e9ece3'),
    ]:
        fig.add_trace(go.Bar(
            y=labels, x=values, orientation='h', name=name, marker_color=color,
            text=[f'{value:.0f}%' if name == 'Available' and value >= 15 else '' for value in values],
            textposition='inside', insidetextanchor='end', textfont={'color': '#fff', 'size': 11},
            customdata=np.column_stack([totals, np.full(len(columns), len(frame))]),
            hovertemplate='%{y}<br>' + name + ': %{customdata[0]:,} / %{customdata[1]:,}'
                          + ' libraries (%{x:.1f}%)<extra></extra>',
        ))
    figure_base(fig, 360)
    fig.update_layout(barmode='stack', bargap=.4, margin={'l': 85, 'r': 22, 't': 15, 'b': 70},
                      legend={'orientation': 'h', 'y': -.2, 'x': 0, 'font': {'size': 10}})
    fig.update_xaxes(range=[0, 100], ticksuffix='%', dtick=25, title=None)
    fig.update_yaxes(autorange='reversed', showgrid=False, tickfont_size=11)
    return fig


def graph(graph_id, **kwargs):
    heights = {'library-map': 430, 'collection-chart': 310,
               'comparison-chart': 350, 'correlation-chart': 350,
               'regional-chart': 360, 'coverage-chart': 360}
    return dcc.Graph(id=graph_id, config=GRAPH_CONFIG, responsive=True,
                     style={'height': heights[graph_id], 'width': '100%'}, **kwargs)


def field(label, control, help_text=None):
    return html.Div([html.Label(label, htmlFor=control.id), control,
                     html.Small(help_text) if help_text else None], className='filter-field')


def card_title(kicker, title, description=None):
    return html.Div([html.Span(kicker, className='eyebrow'), html.H3(title),
                     html.P(description) if description else None], className='card-heading')


def stat(label, value_id, hint_id, accent=False):
    return html.Div([html.Span(label, className='stat-label'), html.Strong(id=value_id),
                     html.Span(id=hint_id, className='stat-hint')], className='stat-card accent' if accent else 'stat-card')


def detail_panel(library=None):
    if library is None:
        return html.Div([
            html.Span('↗', className='detail-icon'),
            html.Div([html.Strong('Every point has a story.'),
                      html.P('Select a library on the map, scatter plot, or table to explore its details.')]),
        ], className='detail-placeholder')
    def item(label, value):
        return html.Div([html.Span(label), html.Strong(value)], className='detail-item')
    return html.Div([
        html.Div([html.Span('SELECTED LIBRARY', className='eyebrow'), html.H3(library['name']),
                  html.P(f"{library['city']} · {library['department']}"),
                  html.Small(str(library['address']) if pd.notna(library['address']) else 'Address not reported')], className='detail-name'),
        html.Div([item('Books', number(library.books)), item('Loans', number(library.loans)),
                  item('Borrowers', number(library.borrowers)), item('Visits', number(library.visits)),
                  item('Income indicator', '€' + number(library.income) if pd.notna(library.income) else 'Not matched'),
                  item('Rent / m²', '€' + number(library.rent, 2) if pd.notna(library.rent) else 'Not matched')], className='detail-values'),
        html.Small(f"Library {library['id']} · INSEE {library['commune_code']} · Missing values are not zero.", className='detail-footnote'),
    ], className='detail-content')


app = Dash(__name__, assets_folder=str(Path(__file__).resolve().parent / 'assets'), title='DALAS · Dataset dashboard', update_title='Updating view…')
server = app.server

app.layout = html.Div([
    dcc.Store(id='filtered-ids'), dcc.Store(id='detail-scroll'), dcc.Download(id='download-data'),
    html.A('Skip to dashboard', href='#atlas', className='skip-link'),
    html.Header([
        html.Nav([html.A('Atlas', href='#atlas'), html.A('Relationships', href='#relationships'), html.A('Data & methods', href='#data')], **{'aria-label': 'Page sections'}),
        html.Span('DALAS / DATA EXPLORATION', className='header-tag'),
    ], className='topbar'),
    html.Div([
        html.Aside([
            html.Div([html.Span('YOUR EXPLORATION', className='eyebrow'), html.H2('Find your focus'),
                      html.P('Filter once. Explore across every view.')], className='sidebar-heading'),
            field('Search libraries', dcc.Input(id='search', type='search', placeholder='Name, commune, INSEE…', debounce=.35, value='', className='search-input')),
            field('Region', dcc.Dropdown(id='regions', options=sorted(LIBRARIES.region.unique()), value=[], multi=True, placeholder='All regions')),
            field('Department', dcc.Dropdown(id='departments', options=sorted(LIBRARIES.department.unique()), value=[], multi=True, placeholder='All departments')),
            field('Collection size', dcc.Dropdown(id='collection', options=[
                {'label': 'All collections', 'value': 'all'}, {'label': 'Under 5,000 books', 'value': 'small'},
                {'label': '5,000–24,999 books', 'value': 'medium'}, {'label': '25,000+ books', 'value': 'large'},
                {'label': 'Not reported', 'value': 'missing'},
            ], value='all', clearable=False)),
            field('Data availability', dcc.Dropdown(id='reporting', options=[
                {'label': 'Include all libraries', 'value': 'all'},
                {'label': 'Selected activity reported', 'value': 'activity'},
                {'label': 'Income & rent matched', 'value': 'context'},
            ], value='all', clearable=False)),
            html.Button('Reset filters ↺', id='reset-filters', className='reset-button', n_clicks=0),
            html.Div([html.Span(className='status-dot'), html.Span(id='sidebar-count')], className='filter-count', **{'aria-live': 'polite'}),
            html.Div([html.Span('A NOTE ON THE DATA', className='eyebrow'),
                      html.P('One point, one library. Repeated postal-code links are counted once.'),
                      html.A('How this dataset was built ↗', href='#methods')], className='sidebar-note'),
            html.Div([html.Span('LOCAL DATASET'), html.Strong(f"{DATASET['communes']:,} commune rows"),
                      html.Small('6 source datasets · France')], className='sidebar-footer'),
        ], className='sidebar'),
        html.Main([
            html.Section([
                html.Div([html.Div([html.Span(className='tiny-line'), 'CULTURE, PLACE & LOCAL CONTEXT'], className='hero-eyebrow'),
                          html.H1(['A closer look at ', html.Em('reading in France.')]),
                          html.P('Explore library collections, activity, and the places around them. Start with the map, then follow the relationships.')], className='hero-copy'),
                html.Div([html.Span('EXPLORING'), html.Strong(id='scope-label'),
                          html.Small('Libraries retained in the merged dataset')], className='scope-card'),
            ], className='hero', id='atlas'),
            html.Div([
                html.Div([html.Span('ACTIVITY MEASURE', className='eyebrow'),
                          dcc.RadioItems(id='metric', options=[{'label': 'Loans', 'value': 'loans'}, {'label': 'Borrowers', 'value': 'borrowers'}, {'label': 'Visits', 'value': 'visits'}], value='loans', inline=True, className='segmented')], className='activity-switch'),
                html.Span('All summaries follow your filters', className='toolbar-note'),
            ], className='view-toolbar'),
            html.Div([
                stat('Libraries in view', 'stat-libraries', 'hint-libraries', True),
                stat('Median collection', 'stat-books', 'hint-books'),
                stat('Median activity', 'stat-activity', 'hint-activity'),
                stat('Activity reporting', 'stat-reporting', 'hint-reporting'),
            ], className='stats-grid'),
            html.Div(id='empty-state', role='status'),
            dcc.Loading(html.Div([
                html.Section([
                    html.Div([card_title('01 / GEOGRAPHY', 'The library landscape', 'Explore locations. Select a point to see the library behind it.'),
                              html.Div([field('Colour by', dcc.Dropdown(id='map-color', options=[{'label': LABELS[c], 'value': c} for c in ['books', 'loans', 'borrowers', 'visits', 'income', 'rent']], value='books', clearable=False))], className='map-color-control')], className='card-top'),
                    html.Div([dcc.RadioItems(id='map-extent', options=[{'label': 'Metropolitan France', 'value': 'mainland'}, {'label': 'All territories', 'value': 'all'}], value='mainland', inline=True, className='map-toggle'),
                              dcc.Checklist(id='offline-map', options=[{'label': 'No basemap', 'value': 'offline'}], value=[], className='offline-toggle')], className='map-tools'),
                    graph('library-map'), html.P(id='map-note', className='chart-note'),
                ], className='panel map-panel'),
                html.Section([
                    card_title('02 / COLLECTIONS & USE', 'From shelves to activity', 'How does typical activity vary with collection size?'),
                    graph('collection-chart'),
                    html.P('Collection bands in books. Bars show the median among libraries reporting both measures; hover for sample sizes.', className='chart-note'),
                    html.Div([html.Span('READING THE CHART', className='eyebrow'), html.P('Medians keep a few very large libraries from dominating the comparison.')], className='insight-note'),
                ], className='panel collection-panel'),
            ], className='atlas-grid'), type='circle', color=TEAL, delay_show=250),
            html.Section(id='library-detail', children=detail_panel(), className='detail-panel', **{'aria-live': 'polite'}),
            html.Section([
                html.Div([html.Div([html.Span('GO A LITTLE DEEPER', className='eyebrow'), html.H2('Explore the relationships')]),
                          html.P('Patterns in the data, without assuming cause and effect.')], className='section-heading'),
                dcc.Loading(html.Div([
                    html.Section([
                        card_title('03 / COMPARE LIBRARIES', 'Resources, context & activity'),
                        html.Div([field('Compare activity with', dcc.Dropdown(id='compare-x', options=[{'label': LABELS[c], 'value': c} for c in ['books', 'population', 'income', 'rent']], value='books', clearable=False)),
                                  field('Axis scale', dcc.Dropdown(id='axis-scale', options=[{'label': 'Logarithmic', 'value': 'log'}, {'label': 'Linear', 'value': 'linear'}], value='log', clearable=False))], className='comparison-controls'),
                        graph('comparison-chart'), html.P(id='comparison-note', className='chart-note'),
                        html.P('Log axes make small and large libraries readable together. Switch to linear to include zero values.', className='chart-note secondary-note'),
                    ], className='panel'),
                    html.Section([
                        card_title('04 / ASSOCIATIONS', 'Which measures move together?', 'Rank correlations for seven relevant measures.'),
                        graph('correlation-chart'),
                        html.P('Spearman ρ · Green: positive association; terracotta: negative. Blank cells have fewer than 10 pairs or a constant measure. Hover for paired counts.', className='chart-note'),
                        html.P('Income and rent appear only where source commune codes match. Correlation does not imply causation.', className='chart-note secondary-note'),
                    ], className='panel'),
                    html.Section([
                        card_title('05 / LOCAL PATTERNS', 'Activity across areas', 'Compare typical activity and the spread between libraries.'),
                        graph('regional-chart'), html.P(id='regional-note', className='chart-note'),
                        html.P('Dots show medians; lines span the middle 50% of reported values, not confidence intervals. Select one region to compare its departments. Library size and reporting differ across areas.', className='chart-note secondary-note'),
                    ], className='panel'),
                    html.Section([
                        card_title('06 / DATA COVERAGE', 'What can we compare?', 'See which measures are available within your current selection.'),
                        graph('coverage-chart'),
                        html.P('Every bar uses all selected libraries as its denominator. Valid zero values count as available; missing values do not mean zero activity.', className='chart-note'),
                        html.P('Income and rent require a matching source commune code. Availability filters also change this view.', className='chart-note secondary-note'),
                    ], className='panel'),
                ], className='relationships-grid'), type='circle', color=TEAL, delay_show=250),
            ], id='relationships'),
            html.Section([
                html.Div([html.Div([html.Span('BEHIND THE VISUALS', className='eyebrow'), html.H2('Explore the records'), html.P(id='table-note')]),
                          html.Button('↓  Download filtered CSV', id='download-button', n_clicks=0, className='download-button')], className='section-heading'),
                html.Div(dag.AgGrid(
                    id='library-table', className='ag-theme-alpine',
                    columnDefs=[{'field': c, 'headerName': LABELS[c], 'minWidth': 110,
                                 **({'flex': 2, 'minWidth': 230} if c == 'name' else {'flex': 1}),
                                 **({'type': 'numericColumn', 'valueFormatter': {'function': "params.value == null ? '—' : d3.format(',.0f')(params.value)"}} if c in ['books', 'loans', 'borrowers', 'visits'] else {})}
                                for c in ['name', 'city', 'department', 'books', 'loans', 'borrowers', 'visits']],
                    defaultColDef={'sortable': True, 'resizable': True},
                    dashGridOptions={'pagination': True, 'paginationPageSize': 15,
                                     'paginationPageSizeSelector': [15, 30, 60],
                                     'rowSelection': {'mode': 'singleRow', 'checkboxes': False, 'enableClickSelection': True},
                                     'animateRows': False, 'rowHeight': 44, 'headerHeight': 44},
                    getRowId='params.data.id', rowData=[], style={'height': '460px'},
                ), className='table-wrap'),
                html.Details([
                    html.Summary([html.Span('About the data & methodology'), html.Span('Read before interpreting ↗')]),
                    html.Div([
                        html.Div([html.H3('A focused view of the merged dataset'),
                                  html.P(f"The file contains {DATASET['communes']:,} commune rows and 190 columns from six sources: geography, rent, income, libraries, bookshops, and population history. This dashboard focuses on {DATASET['libraries']:,} distinct library IDs and their available context."),
                                  html.P('The original postal-code merge kept the first non-null value per field. A postal code can cover several communes and source records can be combined. This subset is not a census of French libraries; missing records do not mean no local library exists.')]),
                        html.Div([html.H3('Locations and context'),
                                  html.P('Library records are deduplicated by source library ID. Coordinates come from the library fields. Region, department, and population use the library’s INSEE commune code; source library labels are fallbacks.'),
                                  html.P('Income and rent are matched separately using their own source commune codes. Values from a neighbouring commune sharing a postal code are not assigned. Deduplication cannot undo composite records created upstream.')]),
                        html.Div([html.H3('Measures and missing values'),
                                  html.P('Books describe collection size; loans, borrowers, and visits describe reported activity. The merged file does not preserve a common observation year or establish individual reading habits.'),
                                  html.P('Income is the source field income_[DEC] Méd (declared-income median indicator); its exact statistical unit and vintage need source documentation. Rent is rent_loypredm2 in €/m². Do not interpret their ratio as affordability.')]),
                        html.Div([html.H3('How the charts are calculated'),
                                  html.P('Missing, non-finite, and negative count values are excluded, never replaced with zero. Valid zero counts remain. Map colour uses log(1 + value) for counts, with a fixed scale across filters; grey means not reported.'),
                                  html.P('The collection chart uses medians and available pairs. The heatmap uses Spearman rank correlation and at least 10 available pairs per cell. Context values may be shared by libraries in the same commune, so observations are not fully independent.')]),
                    ], className='methods-grid'),
                ], id='methods', className='methods'),
            ], id='data'),
        ], className='main-content'),
    ], className='app-body'),
])


@app.callback(
    Output('departments', 'options'), Output('departments', 'value'),
    Input('regions', 'value'), State('departments', 'value'),
)
def update_departments(regions, selected):
    subset = LIBRARIES[LIBRARIES.region.isin(regions)] if regions else LIBRARIES
    options = sorted(subset.department.unique())
    return options, [value for value in (selected or []) if value in options]


@app.callback(
    Output('regions', 'value'), Output('search', 'value'),
    Output('collection', 'value'), Output('reporting', 'value'),
    Output('departments', 'value', allow_duplicate=True),
    Input('reset-filters', 'n_clicks'), prevent_initial_call=True,
)
def reset_filters(_):
    return [], '', 'all', 'all', []


@app.callback(
    Output('filtered-ids', 'data'), Output('scope-label', 'children'),
    Output('sidebar-count', 'children'), Output('empty-state', 'children'),
    Input('regions', 'value'), Input('departments', 'value'), Input('search', 'value'),
    Input('collection', 'value'), Input('reporting', 'value'), Input('metric', 'value'),
)
def apply_filters(regions, departments, search, collection, reporting, metric):
    frame = filter_libraries(LIBRARIES, regions, departments, search, collection, reporting, metric)
    scope = regions[0] if regions and len(regions) == 1 else f'{len(regions)} regions' if regions else 'All of France'
    message = html.Div([html.Strong('No libraries match this selection.'),
                        html.Span(' Broaden your search or reset the filters to start again.')], className='empty-banner') if frame.empty else None
    return frame.index.tolist(), scope, f'{len(frame):,} of {len(LIBRARIES):,} libraries', message


def selected_frame(ids):
    return LIBRARIES.loc[ids] if ids is not None else LIBRARIES


@app.callback(
    Output('stat-libraries', 'children'), Output('hint-libraries', 'children'),
    Output('stat-books', 'children'), Output('hint-books', 'children'),
    Output('stat-activity', 'children'), Output('hint-activity', 'children'),
    Output('stat-reporting', 'children'), Output('hint-reporting', 'children'),
    Output('collection-chart', 'figure'), Output('correlation-chart', 'figure'),
    Output('library-table', 'rowData'), Output('table-note', 'children'),
    Input('filtered-ids', 'data'), Input('metric', 'value'),
)
def update_summaries(ids, metric):
    frame = selected_frame(ids)
    n = len(frame)
    reported = int(frame[metric].notna().sum())
    columns = ['id', 'name', 'city', 'department', 'books', 'loans', 'borrowers', 'visits']
    rows = frame[columns].astype(object).where(frame[columns].notna(), None).to_dict('records')
    return (
        number(n), f"{frame.region.nunique()} {'region' if frame.region.nunique() == 1 else 'regions'} represented",
        number(frame.books.median()) if n else '—', f'books · {frame.books.notna().sum():,} reported',
        number(frame[metric].median()) if n else '—', f'{metric} · {reported:,} reported',
        f'{reported / n:.0%}' if n else '—', f'{n - reported:,} missing {metric} values',
        band_figure(frame, metric), heatmap_figure(frame), rows,
        f'{n:,} unique library records · Click a row for details; click column headings to sort.',
    )


@app.callback(
    Output('library-map', 'figure'), Output('map-note', 'children'),
    Input('filtered-ids', 'data'), Input('map-color', 'value'),
    Input('map-extent', 'value'), Input('offline-map', 'value'),
)
def update_map(ids, color, extent, offline):
    fig, note = map_figure(selected_frame(ids), color, extent, 'offline' if offline else 'streets')
    if offline:
        note += ' · Basemap hidden; coordinates remain interactive'
    else:
        note += ' · Basemap requires internet'
    return fig, note


@app.callback(
    Output('comparison-chart', 'figure'), Output('comparison-note', 'children'),
    Input('filtered-ids', 'data'), Input('compare-x', 'value'),
    Input('metric', 'value'), Input('axis-scale', 'value'),
)
def update_comparison(ids, x, metric, scale):
    return scatter_figure(selected_frame(ids), x, metric, scale)


@app.callback(
    Output('regional-chart', 'figure'), Output('regional-note', 'children'),
    Output('coverage-chart', 'figure'),
    Input('filtered-ids', 'data'), Input('metric', 'value'),
)
def update_area_coverage(ids, metric):
    frame = selected_frame(ids)
    regional, note = regional_figure(frame, metric)
    return regional, note, coverage_figure(frame)


@app.callback(
    Output('library-detail', 'children'),
    Input('library-map', 'clickData'), Input('comparison-chart', 'clickData'),
    Input('library-table', 'selectedRows'), Input('filtered-ids', 'data'),
)
def update_detail(map_click, scatter_click, rows, ids):
    if ctx.triggered_id == 'filtered-ids':
        return detail_panel()
    library_id = None
    click = map_click if ctx.triggered_id == 'library-map' else scatter_click if ctx.triggered_id == 'comparison-chart' else None
    if click and click.get('points'):
        library_id = click['points'][0].get('customdata', [None])[0]
    elif ctx.triggered_id == 'library-table' and rows:
        library_id = rows[0]['id']
    frame = selected_frame(ids)
    match = frame[frame.id.eq(library_id)]
    return detail_panel(match.iloc[0]) if len(match) else detail_panel()


@app.callback(
    Output('download-data', 'data'), Input('download-button', 'n_clicks'),
    State('filtered-ids', 'data'), prevent_initial_call=True,
)
def download_filtered(n_clicks, ids):
    if not n_clicks:
        return no_update
    frame = export_frame(selected_frame(ids)).copy()
    for column in frame.select_dtypes(include=['object', 'string']).columns:
        frame[column] = frame[column].map(lambda value: "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value)
    return dcc.send_data_frame(frame.to_csv, 'filtered-libraries.csv', index=False, encoding='utf-8-sig')


app.clientside_callback(
    """function(content) {
        if (content && content.props && content.props.className === 'detail-content') {
            requestAnimationFrame(function() {
                document.getElementById('library-detail').scrollIntoView({block: 'center', behavior: 'auto'});
            });
        }
        return window.dash_clientside.no_update;
    }""",
    Output('detail-scroll', 'data'), Input('library-detail', 'children'),
    prevent_initial_call=True,
)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Explore the local French library dataset.')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8050)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)
