import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from bokeh.plotting import figure, show
from bokeh.models import ColumnDataSource, LinearAxis, Range1d, Band
from bokeh.models import HoverTool, DatetimeTickFormatter, DateFormatter
from bokeh.tile_providers import get_provider, Vendors
from scipy.spatial.distance import cdist
from bokeh.events import Tap
#from bokeh.models.renderers import GlyphRenderer
#from bokeh.models.widgets import DataTable, TableColumn, Slider, Dropdown
from bokeh.layouts import layout, column, row, widgetbox
from bokeh.io import output_file, save
from bokeh.models.widgets import Panel, Tabs


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
    for column in df.columns:
        df[df[column] == -99.9] = np.nan
    return df



##### Plot 1
def upper_plot(df):
    p1_tools = 'box_zoom,pan,save,hover,reset,wheel_zoom'
    p1 = figure(x_axis_type="datetime", tools=p1_tools);
    h_line = p1.line(x='time', y='tl', source=df, line_width=1.5, color='red');
    p1.y_range=Range1d(df['tp'].min()-2, df['tl'].max()+2)
    p1.line(x='time', y='tp', source=df, line_width=1.5, color='green')
    p1.extra_y_ranges = {'ssd': Range1d(start=0, end=10)}
    p1.add_layout(LinearAxis(y_range_name='ssd'), 'right')
    p1.vbar(top='so', x='time', source=df, width=get_width(), fill_color='yellow', 
            line_alpha=0, line_width=0, fill_alpha=0.4, y_range_name='ssd')
    
    hover_p1 = p1.select(dict(type=HoverTool))
    
    hover_p1.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"), 
                         ('Air temperature', '@tl'), 
                         ('Dewpoint', '@tp'), 
                         ('Sunshine duration', '@so')]#
    hover_p1.formatters = { "time": "datetime"}
    hover_p1.mode = 'vline'
    hover_p1.renderers =[h_line] #### to fix if missing value
    return p1


##### Plot 2
def lower_plot(df):
    p2_tools = 'box_zoom,pan,save,hover,reset,wheel_zoom'
    p2 = figure(x_axis_type="datetime", tools=p2_tools);
    
    
    h_line = p2.line(x='time', y='p', source=df, line_width=1.5, color='black')
    p2.y_range=Range1d(df['p'].min()-10, df['p'].max()+10)
    #p2.extra_y_ranges = {'winddir': Range1d(start=0, end=360)}
    p2.extra_y_ranges = {"winddir": Range1d(start=0, end=360), 
                         "windspd": Range1d(start=0, end=df['ff'].max()+df['ff'].max()*0.1)}
    p2.add_layout(LinearAxis(y_range_name='winddir'), 'right')
    p2.add_layout(LinearAxis(y_range_name="windspd"), 'right')
    p2.line(x='time', y='dd', source=df, line_width=1.5, color='blue', y_range_name='winddir')
    p2.line(x='time', y='ff', source=df, line_width=1.5, color='red', y_range_name='windspd')
    hover_p2 = p2.select(dict(type=HoverTool))
    
    hover_p2.tooltips = [("Timestamp", "@time{%Y-%m-%d %H:%M}"), 
                         ('Pressure', '@p'), 
                         ('Winddirection', '@dd'),
                         ('Windspeed', '@ff')]
    hover_p2.formatters = { "time": "datetime"}
    hover_p2.mode = 'vline'
    hover_p2.renderers =[h_line] #### to fix if missing value
    return p2



#### Setting Up 
output_file("acinn_weather_plot.html")
base_url = 'http://meteo145.uibk.ac.at/'
time = str(3)

# If station selection changes, change this dataframe
stations = pd.DataFrame({'lat':[47.263631,47.011203], 
                         'lon':[11.385571,11.480401]}, 
                         index=['innsbruck', 'obergurgl']) # todo more & correct coordinates obergurgl=sattelberg

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
    p2[station] = lower_plot(df)
    tab.append(Panel(child=column(p1[station], p2[station]), title=station.capitalize()))


#### Layout and save
doc_layout = layout(children=[map_plot, Tabs(tabs=[ tab[0], tab[1] ])])
save(doc_layout)