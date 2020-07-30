import streamlit as st
import pydeck as pdk
import pandas as pd

import momepy
import geopandas as gp
from shapely import wkt
from shapely.geometry import LineString

from sklearn.neighbors import KDTree
import networkx as nx

import requests
from PIL import Image

def OpenData(fileName):
    data=pd.read_csv(fileName)
    return data

def Weight(lenght,tree_label,acc_label,tree_w=0.1,acc_w=0.2):
    if acc_label==3 or acc_label==2:
        return lenght*(1+acc_w*acc_label)
    else:
        return lenght*(1+acc_w*acc_label)*(1-tree_w*tree_label)

# parse the datafrma to geodataframe
def GeoData(data):
    # create a new column lenght weighted by preferences
    data['Lenght_weighted'] = data[['Lenght', 'label_trees', 'labels_acc']].apply(lambda x: Weight(*x), axis=1)

    # create a column with the variation from original lenght and weighted lenght
    data['var_len'] = data.Lenght / data.Lenght_weighted

    df_geo = gp.GeoDataFrame(data)
    df_geo.geometry = df_geo.geometry.astype(str).apply(wkt.loads)
    df_geo = gp.GeoDataFrame(df_geo, geometry='geometry', crs='EPSG:3043')

    return df_geo

#call google APi and get coords from destination and source
def get_geocords(address):
    GOOGLE_MAPS_API_URL = 'https://maps.googleapis.com/maps/api/geocode/json'
    api_key = 'AIzaSyBsBTB1fNkW8K6PK38nmPRZDbafSGU76o0'
    params = {
            'address': address,
            'sensor': 'false',
            'region': 'spain',
            'key': api_key
        }
    req = requests.get(GOOGLE_MAPS_API_URL, params=params)
    res = req.json()
    result = res['results'][0]
    lat = result['geometry']['location']['lat']
    long = result['geometry']['location']['lng']
    return (lat,long)

def ClipData(From, To, data):
    # create data frame with source and dest to clipp map
    ID = [1, 2]
    # TODO: should we create a TRY EXPECT or something? bad adresses?
    Source = get_geocords(From)
    Destination = get_geocords(To)

    Lat1, Long1 = Source
    Lat2, Long2 = Destination
    Lat = [Lat1, Lat2]
    Long = [Long1, Long2]

    df = pd.DataFrame()
    df['id_trip'] = ID
    df['Lat'] = Lat
    df['Long'] = Long

    # pass as a geodata frame, change crs to metters so we buffer and
    # clipp the original map
    df_geo = gp.GeoDataFrame(df, geometry=gp.points_from_xy(df.Long, df.Lat))
    df_geo.crs = {'init': 'EPSG:4326'}
    df_geo = df_geo.to_crs("epsg:3043")

    trips = df_geo.copy()
    trips['geometry'] = LineString(df_geo.geometry)
    # WHY THIS? is not already in this CRS?
    trips = trips.to_crs("epsg:3043")
    # buffer a kilometer
    trips.geometry = trips.geometry.buffer(1000)

    # clipping
    streets_clipped = gp.sjoin(left_df=data, right_df=trips, how='inner')
    # change crs for folium and networkx
    streets_clipped2 = streets_clipped.to_crs('EPSG:4326')

    return streets_clipped2, Source, Destination

def gdf_to_nx(gdf_network):
    # generate graph from GeoDataFrame of LineStrings
    net = nx.Graph()
    net.graph['crs'] = gdf_network.crs
    fields = list(gdf_network.columns)

    for index, row in gdf_network.iterrows():
        first = row.geometry.coords[0]
        last = row.geometry.coords[-1]

        data = [row[f] for f in fields]
        attributes = dict(zip(fields, data))
        net.add_edge(first, last, **attributes)

    return net

def GetRoutes(From, To):
    nodes, edges, sw = momepy.nx_to_gdf(Graph_streets, points=True, lines=True, spatial_weights=True)
    nodes['x'] = nodes.geometry.apply(lambda p: p.x)
    nodes['y'] = nodes.geometry.apply(lambda p: p.y)

    # Find the nearest nodes
    tree = KDTree(nodes[['y', 'x']], metric='euclidean')

    source_idx = tree.query([Source], k=1, return_distance=False)[0]
    dest_idx = tree.query([Destination], k=1, return_distance=False)[0]

    closest_node_to_source = nodes.iloc[source_idx].index.values[0]
    closest_node_to_dest = nodes.iloc[dest_idx].index.values[0]

    route = nx.shortest_path(Graph_streets, source=list(Graph_streets.nodes())[closest_node_to_source],
                             target=list(Graph_streets.nodes())[closest_node_to_dest], weight='Lenght')
    route_weighted = nx.shortest_path(Graph_streets, source=list(Graph_streets.nodes())[closest_node_to_source],
                                      target=list(Graph_streets.nodes())[closest_node_to_dest],
                                      weight='Lenght_weighted')

    ruta_geo = gp.GeoDataFrame()
    ruta_geo['geometry'] = [LineString(route), LineString(route_weighted)]

    # get the points for each linestring as a list of tuples
    short_route = [[x[0], x[1]] for x in list(ruta_geo.geometry[0].coords)]
    healthy_route = [[x[0], x[1]] for x in list(ruta_geo.geometry[1].coords)]

    return short_route, healthy_route

def visualization_streamlit(short_route, healthy_route):
    df = pd.DataFrame({'name': ['short', 'healthy'],
                       'color': [(255, 0, 0), (0, 255, 0)],
                       'path': [short_route, healthy_route]})

    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v9',
        initial_view_state=pdk.ViewState(
            latitude=41.38879,
            longitude=2.15899,
            zoom=13,
            pitch=50,
        ),

        layers = [
            pdk.Layer(
                type="PathLayer",
                data=df,
                pickable=True,
                width_scale=20,
                width_min_pixels=5,
                get_path='path',
                get_color='color',
            ),
        ],
    ))

if __name__ == '__main__':

    st.title('Healthy Cycling')
    st.write('Please select where to go from and to')
    file = 'BCN_streets_geo.csv'

    user_input_from = st.text_input("From", " ")
    user_input_to = st.text_input("To", " ")

    streets_geo = OpenData(file)

    streets_geo = GeoData(streets_geo)

    streets_clipped2, Source, Destination = ClipData(user_input_from, user_input_to, streets_geo)

    Graph_streets = gdf_to_nx(streets_clipped2)

    short_route, healthy_route = GetRoutes(user_input_from, user_input_to)

    visualization_streamlit(short_route, healthy_route)

    image = Image.open('logo.jpg')
    st.image(image, caption='Healthy Cycling Healthy Life', use_column_width=True)

