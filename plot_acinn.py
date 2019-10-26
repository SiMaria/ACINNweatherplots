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
from bokeh.models.widgets import Panel, Tabs
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
        rrcumday = df.groupby(pd.Grouper(freq='D'))
        df['rrcum'] = rrcumday['rr'].cumsum()
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

##### Plot 1
def upper_plot(df):
    p1_tools = 'box_zoom, pan, save, hover, reset, xwheel_zoom' # zoom bounds auto?
    p1 = figure(width = fwidth, height = fhgt, x_axis_type="datetime", 
                tools=p1_tools, 
                x_range=(pd.to_datetime(df.index[-1])-timedelta(days=1), pd.to_datetime(df.index[-1])));
                
    p1 = set_font_sizes_axis(p1)
    hover_p1 = p1.select(dict(type=HoverTool))
    hover_p1.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"), 
                         ('Temperature', "@tl{f0.00} °C")]#
    # sunshine duration
    if 'so' in df.columns:
        p1.extra_y_ranges = {'ssd': Range1d(start=0, end=10)}
        p1.add_layout(LinearAxis(y_range_name='ssd'), 'right')
        p1.vbar(top='so', x='time', source=df, width=get_width(), fill_color='yellow', 
                line_alpha=0, line_width=0, fill_alpha=0.5, y_range_name='ssd', legend = 'Sunshine duration')
        p1.yaxis[1].axis_label = 'Sunshine duration (min)'
        p1.yaxis[1].axis_label_text_font_size = font_size_label
        p1.yaxis[1].major_label_text_font_size = font_size_ticker
        hover_p1[0].tooltips.append(('Sunshine duration', '@so{int} min per 10 min'))
    
    # temperature
    h_line = p1.line(x='time', y='tl', source=df, line_width=4, color='red', legend='Temperature');
    p1.yaxis[0].axis_label = 'Temperature (°C)'
    
    # dew point
    if 'tp' in df.columns:
        p1.y_range=Range1d(df['tp'].min()-2, df['tl'].max()+2)
        p1.line(x='time', y='tp', source=df, line_width=4, color='green', legend = 'Dewpoint')
        hover_p1[0].tooltips.append(('Dewpoint', '@tp{f0.00} °C'))
    else:
        # relative humidity
        p1.y_range=Range1d(0, 100)
        p1.line(x='time', y='rf', source=df, line_width=4, color='green', legend = 'relative humidity')
        hover_p1[0].tooltips.append(('relative humidity', '@rf{f0.00} %'))
    
    # precipitation (daily accumulated)
    if 'rrcum' in df.columns:
        p1.extra_y_ranges['rrcum'] = Range1d(start=0, end=(df['rrcum'].max() + df['rrcum'].max()*0.1))
        p1.add_layout(LinearAxis(y_range_name='rrcum'), 'right')
        p1.line(x='time', y='rrcum', source=df, line_width=4, color=pcol, y_range_name='rrcum', legend = 'Precipitation')
        hover_p1[0].tooltips.append(('Cumulated rainsum', '@rrcum{f0.00} mm'))
        p1.yaxis[2].axis_label_text_font_size = font_size_label
        p1.yaxis[2].major_label_text_font_size = font_size_ticker
        p1.yaxis[2].major_label_text_color = pcol
        # plot rainrate but hide it by default
        rr = p1.vbar(top='rr', x='time', source=df, width=get_width(), 
                     fill_color='blue', line_alpha=0, 
                     line_width=0, fill_alpha=0.5, 
                     legend = 'Rain rate',  y_range_name='rrcum')
        rr.visible = False
        if df['rrcum'].sum() > 0:       
                p1.yaxis[2].axis_label = 'Precipitation (mm)'
    
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
    p2.y_range=Range1d(df['p'].min()-10, df['p'].max()+10)
    p2.yaxis.axis_label = 'Pressure (hPa)'
    
    # wind
    p2.extra_y_ranges = {"winddir": Range1d(start=0, end=360), 
                         "windspd": Range1d(start=0, end=df['ff'].max()+df['ff'].max()*0.1)}
    
    p2.add_layout(LinearAxis(y_range_name='winddir'), 'right')
    p2.add_layout(LinearAxis(y_range_name="windspd"), 'right')
    p2.circle(x='time', y='dd', source=df, line_width=4, color='black', y_range_name='winddir', legend = 'Wind Direction')
    p2.line(x='time', y='ff', source=df, line_width=2, color='red', y_range_name='windspd', legend = 'Wind speed')
   
    
    p2.yaxis[0].axis_label = 'Pressure (hPa)'
    p2.yaxis[1].axis_label = 'Wind direction (deg)'
    p2.yaxis[2].axis_label = 'Wind speed (ms⁻¹)'
    p2.yaxis[1].axis_label_text_font_size = font_size_label
    p2.yaxis[1].major_label_text_font_size = font_size_ticker
    p2.yaxis[2].axis_label_text_font_size = font_size_label
    p2.yaxis[2].major_label_text_font_size = font_size_ticker
    
    # hover
    hover_p2 = p2.select(dict(type=HoverTool))
    hover_p2.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"), 
                         ('Pressure', '@p'), 
                         ('Winddirection', '@dd'),
                         ('Windspeed', '@ff')]
    hover_p2.formatters = { "time": "datetime"}
    hover_p2.mode = 'vline'
    hover_p2.renderers =[h_line] #### to fix if missing value
    
    # legend
    p2.legend.location = "top_left"
    p2.legend.click_policy="hide"
    p2.legend.label_text_font_size = font_size_legend
    
    p2.yaxis[2].major_label_text_color = ffcol
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
#447.167300, 11.457867
# If station selection changes, change this dataframe
stations = pd.DataFrame({'lat':[47.263631, 47.011203, 46.867521, 47.167300], 
                         'lon':[11.385571, 11.480401, 11.024800, 11.457867]}, 
                         index=['innsbruck', 'sattelberg', 'obergurgl', 'ellboegen']) # todo correct coordinates

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
hover_map.tooltips = [("Station", "@index".capitalize())] # todo capitalize!!!!
hover_map.mode = 'mouse'



####### generating plots for the stations
p1 = {}
p2 = {}
tab = []
for station in stations.index:
    df = read_data(stations['url'].loc[stations.index == station]) 
    p1[station] = upper_plot(df)
    p2[station] = lower_plot(df, p1[station])
    tab.append(Panel(child=column(p1[station], p2[station]), title=station.capitalize()))


#### Layout and save
doc_layout = layout(children=[map_plot, Tabs(tabs=tab)])
save(doc_layout)