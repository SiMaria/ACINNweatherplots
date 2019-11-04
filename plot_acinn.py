import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from bokeh.plotting import figure
from bokeh.models import LinearAxis, Range1d, WheelZoomTool
from bokeh.models import HoverTool, DatetimeTickFormatter, DateFormatter
from bokeh.tile_providers import get_provider, Vendors
#from bokeh.models.renderers import GlyphRenderer
#from bokeh.models.widgets import DataTable, TableColumn, Slider, Dropdown
from bokeh.layouts import layout, column, row, widgetbox, gridplot
from bokeh.io import output_file, save
from bokeh.models.widgets import Panel, Tabs, Div
from bokeh.models.widgets import DateRangeSlider



def get_width():
    '''
    Get vbar with for sunshine duration plot
    '''
    mindate = min(df.index)
    maxdate = max(df.index)
    return 0.8 * (maxdate-mindate).total_seconds()*1000 / len(df.index)

def merc(lat, lon):
    """
    Convert latitude and longitude into x and y position
    """
    r_major = 6378137.000
    x = r_major * np.radians(lon)
    scale = x/lon
    y = 180.0/np.pi * np.log(np.tan(np.pi/4.0 +
        lat * (np.pi/180.0)/2.0)) * scale
    return (x, y)

def read_data(url):
    '''
    Read the data from url, store it into a dataframe and set missing values
    to NaN
    '''
    df = pd.read_json(url.values[0])
    df['time'] = [datetime(1970, 1, 1) + timedelta(milliseconds=ds) for ds in df['datumsec']]
    df = df.set_index('time')
    df = df.drop(columns='datumsec')
    # kick out missing values
    for column in df.columns:
        df[df[column] == -99.9] = np.nan
    # calculate cumulative rainsum
    if 'rr' in df.columns:
        df[df['rr'] < 0] = np.nan # missing value = -599.4000000000001???
        df['rm'] = df['rr'] / 6 # calculate rainsum out of rainrate
        rr_cumday = df.groupby(pd.Grouper(freq='D'))
        df['rr_cum'] = rr_cumday['rm'].cumsum()
    return df

def set_font_sizes_axis(p):
    p.xaxis.axis_label_text_font_size = font_size_label
    p.yaxis.axis_label_text_font_size = font_size_label
    p.xaxis.major_label_text_font_size = font_size_ticker
    p.yaxis.major_label_text_font_size = font_size_ticker
    p.yaxis.major_label_text_font_size = font_size_ticker
    p.xaxis.formatter=DatetimeTickFormatter(
            hours=['%H:%M'],
            days=["%b %d %Y"],)
    p.toolbar.active_scroll = p.select_one(WheelZoomTool)
    return p

def get_stats(df):
    '''
    make datatable with statistics
    '''
    if 'rr_cum' in df.columns:
        df = df.drop(columns='rr_cum')
    # mean
    df = df.rename(columns=nice_col_names)
    df_mean = df.resample('1D').mean()
    df_mean = df_mean.transpose()
    df_mean.columns.name = ''
    # min
    df_min = df.resample('1D').min()
    df_min = df_min.transpose()
    df_min.columns.name = ''
    # max
    cur_val = pd.DataFrame(df.iloc[0])
    cum = df.groupby(pd.Grouper(freq='D'))
    if nice_col_names['so'] in df.columns:
        df[nice_col_names['ssd_cum']] = cum[nice_col_names['so']].cumsum()
    if nice_col_names['rr'] in df.columns:
        df[nice_col_names['rr_cum']] = cum[nice_col_names['rm']].cumsum()
    df_max = df.resample('1D').max()
    df_max = df_max.transpose()
    df_max.columns.name = ''
    # stats
    stats = pd.concat([df_mean, df_min, df_max], keys=['mean', 'min', 'max'])
    stats.columns = stats.columns.strftime('%Y-%m-%d')
    return stats, cur_val

##### Plot 1
def upper_plot(df):
    p1_tools = 'box_zoom, pan, save, hover, reset, xwheel_zoom' # zoom bounds auto?
    p1 = figure(width = fwidth, height = fhgt, x_axis_type="datetime",
                tools=p1_tools,
                x_range=(pd.to_datetime(df.index[-1])-timedelta(days=1), pd.to_datetime(df.index[-1])));

    p1 = set_font_sizes_axis(p1)
    hover_p1 = p1.select(dict(type=HoverTool))
    hover_p1.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"),
                         ('Temperature', "@tl{f0.0} °C")]#
    # sunshine duration
    if 'so' in df.columns:
        p1.extra_y_ranges = {'ssd': Range1d(start=0, end=10)}
        p1.add_layout(LinearAxis(y_range_name='ssd'), 'right')
        p1.vbar(top='so', x='time', source=df, width=get_width(), fill_color=socol,
                line_alpha=0, line_width=0, fill_alpha=0.5, y_range_name='ssd', legend = 'Sunshine duration')
        p1.yaxis[1].axis_label = 'Sunshine duration (min)'
        p1.yaxis[1].axis_label_text_font_size = font_size_label
        p1.yaxis[1].major_label_text_font_size = font_size_ticker
        p1.yaxis[1].major_label_text_color = socol
        hover_p1[0].tooltips.append(('Sunshine duration', '@so{int} min per 10 min'))

    # temperature
    h_line = p1.line(x='time', y='tl', source=df, line_width=4, color=tcol, legend='Temperature');
    p1.yaxis[0].axis_label = 'Temperature (°C)'

    # dew point
    if 'tp' in df.columns:
        p1.y_range=Range1d(df['tp'].min()-2, df['tl'].max()+2)
        p1.line(x='time', y='tp', source=df, line_width=4, color=hcol, legend = 'Dewpoint')
        hover_p1[0].tooltips.append(('Dewpoint', '@tp{f0.0} °C'))
    else:
        # relative humidity
        p1.y_range=Range1d(df['tl'].min()-2, df['tl'].max()+2)
        p1.extra_y_ranges = {'rf': Range1d(start=0, end=100)}
        p1.add_layout(LinearAxis(y_range_name='rf'), 'right')
        p1.line(x='time', y='rf', source=df, line_width=4, color=hcol, legend = 'relative humidity', y_range_name='rf')
        p1.yaxis[1].axis_label = 'Relative humidity (%)'
        p1.yaxis[1].axis_label_text_font_size = font_size_label
        p1.yaxis[1].major_label_text_font_size = font_size_ticker
        p1.yaxis[1].major_label_text_color = hcol
        hover_p1[0].tooltips.append(('relative humidity', '@rf{f0.0} %'))

    # precipitation (daily accumulated)
    if 'rr_cum' in df.columns:
        if df['rr_cum'].sum() > 0: #axis would disappear when there was no rain measured
            p1.extra_y_ranges['rr_cum'] = Range1d(start=0, end=(df['rr_cum'].max() + df['rr_cum'].max()*0.1))
        else:
            p1.extra_y_ranges['rr_cum'] = Range1d(start=0, end=10)
        p1.add_layout(LinearAxis(y_range_name='rr_cum'), 'right')
        p1.line(x='time', y='rr_cum', source=df, line_width=4, color=pcol, y_range_name='rr_cum', legend = 'Precipitation')
        hover_p1[0].tooltips.append(('Cumulated precipitation', '@rr_cum{f0.0} mm'))
        p1.yaxis[2].axis_label_text_font_size = font_size_label
        p1.yaxis[2].major_label_text_font_size = font_size_ticker
        p1.yaxis[2].major_label_text_color = pcol
        p1.yaxis[2].axis_label = 'Precipitation (mm)'
        # plot rainrate but hide it by default
        rr = p1.vbar(top='rr', x='time', source=df, width=get_width(),
                     fill_color='blue', line_alpha=0,
                     line_width=0, fill_alpha=0.5,
                     legend = 'Precipitation rate',  y_range_name='rr_cum')
        rr.visible = False

    # hover
    hover_p1.formatters = { "time": "datetime"}
    hover_p1.mode = 'vline'
    hover_p1.renderers =[h_line] #### to fix if missing value

    # legend
    p1.legend.location = "top_left"
    p1.legend.click_policy="hide"
    p1.legend.label_text_font_size = font_size_legend
    return p1


##### Plot 2
def lower_plot(df, p1):
    p2_tools = 'box_zoom,pan,save,hover,reset,xwheel_zoom'
    p2 = figure(width = fwidth, height = fhgt,x_axis_type="datetime",
                tools=p2_tools, x_range=p1.x_range);

    p2 = set_font_sizes_axis(p2)

    # pressure
    h_line = p2.line(x='time', y='p', source=df, line_width=4, color='blue', legend = 'Pressure')
    p2.y_range=Range1d(df['p'].min()-5, df['p'].max()+5)
    p2.yaxis.axis_label = 'Pressure (hPa)'

    # wind
    p2.extra_y_ranges = {"winddir": Range1d(start=0, end=360),
                         "windspd": Range1d(start=0, end=df['ff'].max()+df['ff'].max()*0.1)}

    p2.add_layout(LinearAxis(y_range_name='winddir'), 'right')
    p2.add_layout(LinearAxis(y_range_name="windspd"), 'right')
    p2.circle(x='time', y='dd', source=df, line_width=4, color='black', y_range_name='winddir', legend = 'Wind Direction')
    p2.line(x='time', y='ff', source=df, line_width=2, color='red', y_range_name='windspd', legend = 'Wind speed')


    p2.yaxis[0].axis_label = 'Pressure (hPa)'
    p2.yaxis[1].axis_label = 'Wind direction (°)'
    p2.yaxis[2].axis_label = 'Wind speed (ms⁻¹)'
    p2.yaxis[1].axis_label_text_font_size = font_size_label
    p2.yaxis[1].major_label_text_font_size = font_size_ticker
    p2.yaxis[2].axis_label_text_font_size = font_size_label
    p2.yaxis[2].major_label_text_font_size = font_size_ticker
    p2.yaxis[2].major_label_text_color = ffcol
    p2.yaxis[0].major_label_text_color = pcol

    # hover
    hover_p2 = p2.select(dict(type=HoverTool))
    hover_p2.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"),
                         ('Pressure', '@p{f0.0} hPa'),
                         ('Winddirection', '@dd{int} °'),
                         ('Windspeed', '@ff{f0.0} (ms⁻¹)')]
    hover_p2.formatters = { "time": "datetime"}
    hover_p2.mode = 'vline'
    hover_p2.renderers =[h_line] #### to fix if missing value

    # legend
    p2.legend.location = "top_left"
    p2.legend.click_policy="hide"
    p2.legend.label_text_font_size = font_size_legend
    return p2



#### Setting Up
output_file("acinn_weather_plot.html")
base_url = 'http://meteo145.uibk.ac.at/'
time = str(7)
fwidth = 900
fhgt = 400
font_size_label = "20pt"
font_size_ticker = "15pt"
font_size_legend = "12pt"
ffcol = 'red'
ddcol = 'black'
pcol = 'blue'
hcol = 'green'
tcol = 'red'
socol = 'gold'


nice_col_names = {
    'dd' : 'Wind direction (deg)',
    'ff' : 'Wind speed (m/ s)',
    'p' : 'Pressure (hPa)',
    'rr' : 'Precipitation rate (mm/ h)',
    'rm' : 'Precipitation (mm per 10 min)',
    'so' : 'Sunshine duration (min per 10 min)',
    'tl' : 'Temperature (°C)',
    'tp' : 'Dewpoint (°C)',
    'rf' : 'Relative humidity (%)',
    'rr_cum' : 'Cumulated precipitation (mm)',
    'ssd_cum' : 'Cumulated sunshine duration (min)',
}
#447.167300, 11.457867
# If station selection changes, change this dataframe
stations = pd.DataFrame({'lat':[47.260, 47.011, 46.867, 47.187],
                        'lon':[11.384, 11.479, 11.024, 11.429],
                        'height':[578, 2107, 1942, 1080],
                        },
                        index=['innsbruck', 'sattelberg', 'obergurgl', 'ellboegen']) # coordinates based on metinf
# lazy workaround for capital station name in map
stations['cap_station'] = stations.index.str.capitalize()

#### Template for Tab formatting
# Attention: works for Bokeh v1.3.4, might not work with other versions (e.g. below  v1.1.0)
template = """
{% block postamble %}
<style>
.bk-root .bk-tab {
    background-color: white;
    width: 200px;
    color: black;
    font-style: italic;
    font-size: 20pt
}
.bk-root .bk-tabs-header .bk-tab.bk-active{
    background-color: white;
    color: black;
    font-style: normal;
    font-weight: bold;
    font-size: 20pt
}
.bk-root .bk-tabs-header .bk-tab:hover{
    background-color: white
}
</style>
{% endblock %}
"""


# filling url column
stations['url'] = ''
for station in stations.index:
    url = base_url + station + '/' + time
    stations['url'].loc[stations.index == station] = url

# calculating x and y positions
[stations['x'], stations['y']] = merc(stations['lat'], stations['lon'])


#### Mapplot
tile_provider = get_provider(Vendors.CARTODBPOSITRON)
map_tools = 'box_zoom,pan,save,hover,reset,wheel_zoom'
map_plot = figure(x_range=(1108137, 1417582), y_range=(5895123 , 6088551),
                  plot_width=600, plot_height=350,
                  x_axis_type="mercator", y_axis_type="mercator",
                  tools=map_tools)
map_plot.add_tile(tile_provider)
map_plot.circle(x="x", y="y", size=15, fill_color="blue",
                fill_alpha=0.5, source=stations);
hover_map = map_plot.select(dict(type=HoverTool))
hover_map.tooltips = [("Station", "@cap_station"), # todo capitalize!!!!
                      ('Height', '@height m')]
hover_map.mode = 'mouse'
map_plot.yaxis[0].axis_label = 'Latitude (°)'
map_plot.xaxis[0].axis_label = 'Longitude (°)'
map_plot.yaxis[0].axis_label_text_font_size = font_size_label
map_plot.yaxis[0].major_label_text_font_size = font_size_ticker
map_plot.xaxis[0].axis_label_text_font_size = font_size_label
map_plot.xaxis[0].major_label_text_font_size = font_size_ticker


####### generating plots for the stations
p1 = {}
p2 = {}
sts = {}
tab = []
for station in stations.index:
    df = read_data(stations['url'].loc[stations.index == station])
    [stats, cur_val] = get_stats(df)
    stats = stats.round(decimals=1)
    p1[station] = upper_plot(df)
    p2[station] = lower_plot(df, p1[station])
    sts[station] =  Div(text='''<p style="font-size:20px;">Current values:</p> {}
                                <p style="font-size:20px;">Statistics:</p> {}
                                '''.format(cur_val.to_html(),stats.to_html()))
    tab.append(Panel(child=column(p1[station], p2[station], sts[station]),
                     title=station.capitalize()))


#### Layout and save
doc_layout = layout(children=[map_plot, Tabs(tabs=tab)])
save(doc_layout, template = template)
