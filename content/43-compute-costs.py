import osmnx as ox
import geopandas
import pandas

# create the necessary dataframes for the routing problem
postcodes = pandas.read_csv("./data/uk_postcodes.csv")
postcodes = geopandas.GeoDataFrame(
    postcodes, 
    geometry=geopandas.points_from_xy(
        postcodes.lon, 
        postcodes.lat, 
        crs="epsg:4326"
    )
)
bristol_postcodes = postcodes[postcodes.outward.str.startswith("BS")].copy()
is_inner_city = bristol_postcodes.outward.str.lstrip("BS").astype(int) < 10
bristol_innercity = bristol_postcodes[is_inner_city].copy()
bristol_outercity = bristol_postcodes[~ is_inner_city].copy()

# get the area where we need to pull the OSM graph
west, south, east, north = bristol_postcodes.total_bounds

# actually pull the OSM graph and populate the edge speeds/travel times
graph = ox.graph_from_bbox(north, south, east, west, network_type='drive')
graph = ox.speed.add_edge_speeds(graph)
graph = ox.speed.add_edge_travel_times(graph)

# snap the postcodes to the nearest nodal location on the road for routing
facilities = ox.distance.nearest_nodes(
    graph, 
    bristol_outercity.lon, 
    bristol_outercity.lat
)
clients = ox.distance.nearest_nodes(
    graph, 
    bristol_postcodes.lon, 
    bristol_postcodes.lat
)

# create a results dataframe that stores all pairs of facility-client pairs
all_combinations = pandas.DataFrame.from_records(
    [(fac,cli) for fac in facilities for cli in clients],
    columns=['origin_osmid', 'destination_osmid']
)

# compute the travel time shortest paths over the graph
routes = ox.distance.shortest_path(
    graph, 
    all_combinations.origin_osmid, 
    all_combinations.destination_osmid, 
    weight='travel_time',
    cpus=4 # you may need to change this up or down depending on your platform!
)

# unpack the routes into distances:
path_costs = [
    sum(
        ox.utils_graph.get_route_edge_attributes(
            graph, 
            route, 
            "travel_time"
        )
    )
    for route in routes
]
# save those distances back to our original frame
all_combinations['cost'] = path_costs

# and prepare to save results by postcode, not OSM ID
origin_postcode, destination_postcode = zip(*[(o,d) 
                                              for o in bristol_postcodes.outward 
                                              for d in bristol_postcodes.outward])

all_combinations['origin_postcode'] = origin_postcode
all_combinations['destination_postcode'] = destination_postcode

# save the result
all_combinations[['origin_postcode', 'destination_postcode', 'cost']].to_csv("./cost_table_new.csv")