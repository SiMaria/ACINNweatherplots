import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import math

from bokeh.plotting import figure
from bokeh.models import LinearAxis, Range1d, WheelZoomTool, SingleIntervalTicker, ZoomInTool, ZoomOutTool
from bokeh.models import HoverTool, DatetimeTickFormatter, WMTSTileSource
from bokeh.layouts import layout, column
from bokeh.io import output_file, save
from bokeh.models.widgets import Panel, Tabs, Div
from bokeh.transform import dodge



#### Setup
output_file("acinn_weather_plot.html")
base_url = 'http://meteo145.uibk.ac.at/'
time = str(7)
fwidth = 800
fhgt = 350
fborder = 25
font_size_label = "19pt"
font_size_ticker = "14pt"
font_size_legend = "11pt"
ffcol = 'firebrick' #'#e41a1c'
ddcol = 'black'
pcol = '#0173b2' #'steelblue'
hcol =  'seagreen' #'#029e73'
tcol = 'firebrick'
socol = 'orange'

# plot sunshine duration cumulated (ssdcum = True) or as 10 min values
ssdcum = False
# period to sum up precipitation in minutes (minimum 10)
rrsum_period = 60*3

nice_col_names = {
    'dd' : 'Wind direction (°)',
    'ff' : 'Wind speed (m s⁻¹)',
    'p' : 'Pressure (hPa)',
    'rr' : 'Precipitation rate (mm h⁻¹)',
    'rm' : 'Precipitation (mm in 10 min)',
    'so' : 'Sunshine duration (min in 10 min)',
    'tl' : 'Temperature (°C)',
    'tp' : 'Dewpoint (°C)',
    'rf' : 'Relative humidity (%)',
    'rr_cum' : 'Cumulated precipitation (mm)',
    'ssd_cum' : 'Cumulated sunshine duration (h)',
}
#447.167300, 11.457867
# When station selection changes, change this dataframe
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
    font-size: 18pt
}
.bk-root .bk-tabs-header .bk-tab.bk-active{
    background-color: white;
    color: black;
    font-style: normal;
    font-weight: bold;
    font-size: 18pt
}
.bk-root .bk-tabs-header .bk-tab:hover{
    background-color: white;
}
table.dataframe {
font-size:115%;
text-align: center;
}
table.dataframe th {
    text-align: left;
}
</style>
{% endblock %}
"""

def get_width():
    '''
    Get vbar width for sunshine duration plot
    '''
    mindate = min(df.index)
    maxdate = max(df.index)
    return 0.95 * (maxdate-mindate).total_seconds()*1000 / len(df.index)

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

def round_dec(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier

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
    for col in df.columns:
        df[df[col] == -99.9] = np.nan

    # calculate 3h rainsum and cumulated rain/ sunshine duration
    if 'rr' in df.columns:
        rrsum_rule = str(rrsum_period)+'min'
        df[df['rr'] < 0] = np.nan # missing value = -599.4000000000001???
        df['rm'] = df['rr'] / 6 # calculate rainsum out of rainrate
        df['rr_cum'] = df['rm'].groupby(pd.Grouper(freq='D')).cumsum()
        df['rrsum'] = df['rm'].groupby(pd.Grouper(freq=rrsum_rule, label='right', closed = 'right')).sum()
        df['rrsumm'] = df['rrsum'].fillna(method='bfill')  # fill up for hover
    if 'so' in df.columns:
        df[df['so'] < 0] = np.nan
        ssd_cumday = df.groupby(pd.Grouper(freq='D'))
        df['ssd_cum'] = ssd_cumday['so'].cumsum()/60
    return df

def set_font_style_axis(p):
    p.xaxis.axis_label_text_font_size = font_size_label
    p.yaxis.axis_label_text_font_size = font_size_label
    p.xaxis.major_label_text_font_size = font_size_ticker
    p.yaxis.major_label_text_font_size = font_size_ticker
    p.yaxis.major_label_text_font_size = font_size_ticker
    p.yaxis.axis_label_text_font_style = "normal"
    p.xaxis.axis_label_text_font_style = "normal"
    p.xaxis.formatter=DatetimeTickFormatter(
            hours=['%H:%M'],
            days=["%d %b %Y"],)          #  days=["%d %b"],) without year
    p.toolbar.active_scroll = p.select_one(WheelZoomTool)
    return p

def get_stats(df):
    '''
    make datatable with statistics
    '''
    # for daily actions
    group = df.groupby(pd.Grouper(freq='D'))

    # mean, min and max
    df_mean = df.resample('1D').mean()
    df_min = df.resample('1D').min()
    df_max = df.resample('1D').max()

    # cumulated
    df_cum = df.resample('1D').max()
    df_cum = df_cum.filter(like='cum')

    # current values
    cur_val = pd.DataFrame(df.iloc[-1])
    sortlist = ['tl', 'tp', 'rf', 'ff', 'dd', 'p', 'rr', 'rr_cum', 'ssd_cum']
    sortby = []
    for i in sortlist:
        if i in cur_val.index: sortby.append(i)
    cur_val = cur_val.reindex(sortby)
    cur_val = cur_val.rename(index=nice_col_names)
    cur_val.columns = cur_val.columns.strftime('%d %b %Y %H:%M UTC')

    # vars with max, mean, min statistics
    varlist = ['tl', 'tp', 'rf', 'p', 'ff']
    vars = []
    for i in varlist:
        if i in df.columns: vars.append(i)

    stat = pd.DataFrame()
    for var in vars:
        tmp = pd.DataFrame([df_max[var], df_min[var], df_mean[var]], index = ['max', 'min','mean'])
        tmp = pd.concat([tmp], keys=[var])
        stat = stat.append(tmp)
        del tmp

    # wind direction
    if 'ff' in df.columns and 'dd' in df.columns:
        # direction at wind max
        idx = group['ff'].transform(max) == df['ff'] # find wind direction, corresponding to wind max
        ddx = df['dd'][idx].resample('1D').first() # when ffmax occurs several times, take first ddx
        tmp = pd.DataFrame([ddx], index = [''])
        tmp = pd.concat([tmp], keys=['Wind direcetion (°) at speed max'])
        stat = stat.append(tmp)
        # direction at wind min
        idx = group['ff'].transform(min) == df['ff'] # find wind direction, corresponding to wind min
        ddx = df['dd'][idx].resample('1D').first() # when ffmin occurs several times, take first ddx
        tmp = pd.DataFrame([ddx], index = [''])
        tmp = pd.concat([tmp], keys=['Wind direcetion (°) at speed min'])
        stat = stat.append(tmp)
        del tmp

    # cumulated vars: sunshine and precipitation
    varlist = ['ssd_cum', 'rr_cum']
    vars = []
    for i in varlist:
        if i in df_cum.columns: vars.append(i)

    for var in vars:
        tmp = pd.DataFrame([df_cum[var]], index = [''])
        tmp = pd.concat([tmp], keys=[var])
        stat = stat.append(tmp)
        del tmp

    stats = stat.rename(index=nice_col_names)
    stats.columns = stats.columns.strftime(' %d %b ')
    return stats, cur_val

##### Plot 1
def upper_plot(df):
    # configure wheelzoom tool
    wz = WheelZoomTool()
    wz.maintain_focus = False
    wz.dimensions = 'width'
    wz.zoom_on_axis = True

    p1_tools = 'box_zoom,pan,save, hover, reset'#, xwheel_zoom' # zoom bounds auto?
    p1 = figure(width = fwidth, height = fhgt, x_axis_type="datetime",
                tools=p1_tools)
    p1.x_range = Range1d(start=df.index[-1]-timedelta(days=1), end=df.index[-1],
                         bounds=(df.index[0],df.index[-1]))
    p1.add_tools(wz)
    p1.min_border_top = fborder
    p1.min_border_bottom = fborder

    # hover for temp, dew point and rel. humidity
    hover_p1 = p1.select(dict(type=HoverTool))
    hover_p1.tooltips = [("Timestamp", "@time{%d %b %Y %H:%M} UTC"),
                         ('Temperature', "@tl{f0.0} °C")]#
    if 'tp' in df.columns:
        hover_p1[0].tooltips.append(('Dewpoint', '@tp{f0.0} °C'))
    else:

        hover_p1[0].tooltips.append(('Relative Humidity', '@rf{f0.0} %'))

    # sunshine duration
    if 'so' in df.columns:
        if ssdcum:
            varso = 'ssd_cum' # 'ssd_cum' or 'so'
            unitso = 'h'
        else:
            varso = 'so' # 'ssd_cum' or 'so'
            unitso = 'min'

        if ssdcum and df[varso].sum() > 0: #axis would disappear when there was no rain measured
            p1.extra_y_ranges[varso] = Range1d(start=0, end=(df[varso].max() + df[varso].max()*0.1))
        else:
            p1.extra_y_ranges[varso] = Range1d(start=0, end=10)
        p1.add_layout(LinearAxis(y_range_name=varso), 'right')

        if ssdcum:
            p1.line(x='time', y=varso, source=df, line_width=4, color=socol, y_range_name=varso, legend = 'Sunshine duration (24h)')
        else:
            p1.vbar(top=varso, x='time', source=df, width=get_width(), fill_color=socol,
                    line_alpha=0, line_width=0, fill_alpha=0.5, y_range_name=varso, legend = 'Sunshine duration')

        p1.yaxis[1].axis_label = 'Sunshine duration (' + unitso + ')'
        p1.yaxis[1].axis_label_text_font_size = font_size_label

        p1.yaxis[1].major_label_text_color = socol
        p1.yaxis[1].axis_label_text_color = socol
        p1.yaxis[1].minor_tick_line_color = socol
        p1.yaxis[1].major_tick_line_color = socol
        p1.yaxis[1].axis_line_color = socol
        hover_p1[0].tooltips.append(('Sunshine duration', '@so{int} min per 10 min'))
        hover_p1[0].tooltips.append(('Cumulated sunshine duration', '@ssd_cum{f0.0} h'))

    # temperature
    h_line = p1.line(x='time', y='tl', source=df, line_width=4, color=tcol, legend='Temperature');
    p1.yaxis[0].axis_label = 'Temperature (°C)'
    p1.yaxis[0].major_label_text_color = tcol
    p1.yaxis[0].axis_label_text_color = tcol
    p1.yaxis[0].minor_tick_line_color = tcol
    p1.yaxis[0].major_tick_line_color = tcol
    p1.yaxis[0].axis_line_color = tcol
    p1.yaxis[0].axis_label_text_font_style = "normal"

    # dew point
    if 'tp' in df.columns:
        p1.y_range=Range1d(df['tp'].min()-2, df['tl'].max()+2)
        p1.line(x='time', y='tp', source=df, line_width=4, color=hcol, legend = 'Dewpoint')
    else:
        # relative humidity
        p1.y_range=Range1d(df['tl'].min()-2, df['tl'].max()+2)
        p1.extra_y_ranges = {'rf': Range1d(start=0, end=100)}
        p1.add_layout(LinearAxis(y_range_name='rf'), 'right')
        p1.line(x='time', y='rf', source=df, line_width=4, color=hcol, legend = 'Relative Humidity', y_range_name='rf')
        p1.yaxis[1].axis_label = 'Relative humidity (%)'
        p1.yaxis[1].major_label_text_color = hcol
        p1.yaxis[1].axis_label_text_color = hcol
        p1.yaxis[1].minor_tick_line_color = hcol
        p1.yaxis[1].major_tick_line_color = hcol
        p1.yaxis[1].axis_line_color = hcol

    # precipitation (3 h sums)
    if 'rrsum' in df.columns:
        if df['rrsum'].sum() > 0: #axis would disappear when there was no rain measured
            p1.extra_y_ranges['rrsum'] = Range1d(start=0, end=(df['rrsum'].max()*2))
        else:
            p1.extra_y_ranges['rrsum'] = Range1d(start=0, end=10)
        p1.add_layout(LinearAxis(y_range_name='rrsum'), 'right')

        timeoffset = 0 # timeoffset: dodge to correctly bin bar in time
        if rrsum_period > 10: timeoffset = -60*rrsum_period/2*1000
        rr = p1.vbar(x=dodge('time', timeoffset, range=p1.x_range), top='rrsum', width=get_width()*rrsum_period/10, source=df,
                     fill_color=pcol, line_alpha=0,
                     line_width=0, fill_alpha=0.5,
                     legend = 'Precipitation',  y_range_name='rrsum')
        rr.level='underlay'
        if rrsum_period >= 60:
            rr_period = str(round_dec(rrsum_period/60, decimals=1)) + ' h'
        else:
            rr_period = str(rrsum_period)+' min'
        hover_p1[0].tooltips.append(('Precipitation', '@rrsumm{f0.0} mm in '+rr_period))
        hover_p1[0].tooltips.append(('Cumulated precipitation', '@rr_cum{f0.0} mm'))

        p1.yaxis[2].major_label_text_color = pcol
        p1.yaxis[2].axis_label_text_color = pcol
        p1.yaxis[2].minor_tick_line_color = pcol
        p1.yaxis[2].major_tick_line_color = pcol
        p1.yaxis[2].axis_line_color = pcol
        p1.yaxis[2].axis_label = 'Precipitation (mm)'

    # hover
    hover_p1.formatters = { "time": "datetime"}
    hover_p1.mode = 'vline'
    hover_p1.renderers =[h_line] #### to fix if missing value

    # legend
    p1.legend.location = (0, 15) # above plot
    p1.legend.orientation = 'horizontal'
    p1.legend.click_policy="hide"
    p1.legend.label_text_font_size = font_size_legend
    p1.add_layout(p1.legend[0],'above')

    # font style
    p1 = set_font_style_axis(p1)

    return p1

##### Plot 2
def lower_plot(df, p1):
    # configure wheelzoom tool
    wz = WheelZoomTool()
    wz.maintain_focus = False
    wz.dimensions = 'width'
    wz.zoom_on_axis = True

    p2_tools = 'box_zoom,pan,save, hover, reset'
    p2 = figure(width = fwidth, height = fhgt+35,x_axis_type="datetime",
                tools=p2_tools, x_range=p1.x_range);
    p2.add_tools(wz)
    p2.min_border_top = fborder
    p2.min_border_bottom = fborder

    # pressure
    h_line = p2.line(x='time', y='p', source=df, line_width=4, color=pcol, legend = 'Pressure')
    p2.y_range=Range1d(df['p'].min()-5, df['p'].max()+5)
    p2.yaxis.axis_label = 'Pressure (hPa)'

    # wind
    p2.extra_y_ranges = {"winddir": Range1d(start=0, end=360),
                         "windspd": Range1d(start=0, end=df['ff'].max()+df['ff'].max()*0.1)}

    p2.add_layout(LinearAxis(y_range_name='winddir', ticker=SingleIntervalTicker(interval=45, num_minor_ticks=3)), 'right')
    p2.add_layout(LinearAxis(y_range_name="windspd"), 'right')
    p2.circle(x='time', y='dd', source=df, line_width=4, color='black', y_range_name='winddir', legend = 'Wind Direction')
    p2.line(x='time', y='ff', source=df, line_width=4, color=ffcol, y_range_name='windspd', legend = 'Wind speed')


    p2.yaxis[0].axis_label = 'Pressure (hPa)'
    p2.yaxis[1].axis_label = 'Wind direction (°)'
    p2.yaxis[2].axis_label = 'Wind speed (m s⁻¹)'
    p2.xaxis[0].axis_label = 'Time (UTC)'

    p2.yaxis[2].major_label_text_color = ffcol
    p2.yaxis[2].axis_label_text_color = ffcol
    p2.yaxis[2].minor_tick_line_color = ffcol
    p2.yaxis[2].major_tick_line_color = ffcol
    p2.yaxis[2].axis_line_color = ffcol
    p2.yaxis[0].major_label_text_color = pcol
    p2.yaxis[0].axis_label_text_color = pcol
    p2.yaxis[0].minor_tick_line_color = pcol
    p2.yaxis[0].major_tick_line_color = pcol
    p2.yaxis[0].axis_line_color = pcol

    # hover
    hover_p2 = p2.select(dict(type=HoverTool))
    hover_p2.tooltips = [("Timestamp", "@time{%d %b %Y %H:%M} UTC"),
                         ('Pressure', '@p{f0.0} hPa'),
                         ('Winddirection', '@dd{int} °'),
                         ('Windspeed', '@ff{f0.0} (m s⁻¹)')]
    hover_p2.formatters = { "time": "datetime"}
    hover_p2.mode = 'vline'
    hover_p2.renderers =[h_line] #### to fix if missing value

    # legend
    p2.legend.location = (0, 15) # above plot
    p2.legend.orientation = 'horizontal'
    p2.legend.click_policy="hide"
    p2.legend.label_text_font_size = font_size_legend
    p2.add_layout(p2.legend[0],'above')

    # font style
    p2 = set_font_style_axis(p2)

    #set boarders for zoom
    p2.x_range.max_interval = timedelta(7.5)
    return p2

# filling url column
stations['url'] = ''
for station in stations.index:
    url = base_url + station + '/' + time
    stations['url'].loc[stations.index == station] = url

# calculating x and y positions
[stations['x'], stations['y']] = merc(stations['lat'], stations['lon'])

#### Mapplot
tile_options = {}
tile_options['url'] = 'http://tile.stamen.com/terrain/{Z}/{X}/{Y}.png'
tile_options['attribution'] = """
    Map tiles by <a href="http://stamen.com">Stamen Design</a>, under
    <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a>.
    Data by <a href="http://openstreetmap.org">OpenStreetMap</a>,
    under <a href="http://www.openstreetmap.org/copyright">ODbL</a>.
    """
mq_tile_source = WMTSTileSource(**tile_options)

map_tools = 'box_zoom,pan,save,hover,reset,wheel_zoom'
map_plot = figure(x_range=(1162560, 1435315), y_range=(5898792 , 6018228),
                  plot_width=(fwidth-75), plot_height=fhgt+fborder,
                  x_axis_type="mercator", y_axis_type="mercator",
                  tools=map_tools)
map_plot.min_border_left = 75
map_plot.add_tile(mq_tile_source)
map_plot.circle(x="x", y="y", size=18, fill_color="firebrick",color = 'firebrick',
                fill_alpha=0.7, source=stations);
hover_map = map_plot.select(dict(type=HoverTool))
hover_map.tooltips = [("Station", "@cap_station"), # todo capitalize!!!!
                      ('Height', '@height m')]
hover_map.mode = 'mouse'
map_plot.yaxis[0].axis_label = 'Latitude (°)'
map_plot.xaxis[0].axis_label = 'Longitude (°)'
map_plot.toolbar.active_scroll = map_plot.select_one(WheelZoomTool)
map_plot.xaxis.axis_label_text_font_style = "normal"
map_plot.yaxis.axis_label_text_font_style = "normal"
map_plot.xaxis.axis_label_text_font_size = font_size_label
map_plot.yaxis.axis_label_text_font_size = font_size_label
map_plot.xaxis.major_label_text_font_size = font_size_ticker
map_plot.yaxis.major_label_text_font_size = font_size_ticker

####### generating plots for the stations
p1 = {}
p2 = {}
sts = {}
tab = []
for station in stations.index:
    df = read_data(stations['url'].loc[stations.index == station])
    [stats, cur_val] = get_stats(df)
    cur_val = cur_val.round(decimals=2)
    stats = stats.round(decimals=1)
    cur_val = cur_val.round(decimals=1)
    p1[station] = upper_plot(df)
    p2[station] = lower_plot(df, p1[station])
    sts[station] =  Div(text='''<p style="font-size:24px;font-weight: bold;">Current values:</p> {}
                                <p style="font-size:24px;font-weight: bold;">Statistics:</p> {}
                                '''.format(cur_val.to_html(),stats.to_html()))
    tab.append(Panel(child=column(p1[station], p2[station], sts[station]),
                     title=station.capitalize()))

#### Layout and save
doc_layout = layout(children=[map_plot, Tabs(tabs=tab)])
save(doc_layout, template = template)
