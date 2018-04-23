import config
from . import util
from .csa import CSA
from itertools import product
from collections import namedtuple


# route components
WalkLeg = namedtuple('WalkLeg', ['time'])
TransitLeg = namedtuple('TransitLeg', ['dep_stop', 'arr_stop', 'dep_time', 'arr_time', 'trip_id'])
TransferLeg = namedtuple('TransferLeg', ['dep_stop', 'arr_stop', 'time'])


class NoTransitRouteFound(Exception): pass


class TransitRouter:
    def __init__(self, transit, dt):
        self.T = transit
        self.valid_trips = self.T.calendar.trips_for_day(dt)

        # reduce connections to only those for this day
        connections = [c for c in self.T.connections if self.T.trip_idx.id[c['trip_id']] in self.valid_trips]

        self.csa = CSA(connections, self.T.footpaths, config.BASE_TRANSFER_TIME)

    def route(self, start_coord, end_coord, dep_time, closest_stops=2):
        """compute a trip-level route between
        a start and an end stop for a given datetime"""
        # candidate start and end stops,
        # returned as [(iid, time), ...]
        # NB here we assume people have no preference b/w transit mode,
        # i.e. they are equally likely to choose a bus stop or a subway stop.
        # increasing the closest stops will increase likelihood of finding best
        # route, but also significantly increases routing time
        start_stops = {
            self.T.stop_idx.idx[stop_id]: walk_time for stop_id, walk_time in self.T.closest_stops(start_coord, n=closest_stops)
        }
        end_stops = {
            self.T.stop_idx.idx[stop_id]: walk_time for stop_id, walk_time in self.T.closest_stops(end_coord, n=closest_stops)
        }
        same_stops = set(start_stops.keys()) & set(end_stops.keys())

        # if a same stop is in start and end stops,
        # walking is probably the best option
        if same_stops:
            walk_time = util.walking_time(
                start_coord, end_coord,
                config.FOOTPATH_DELTA_BASE, config.FOOTPATH_SPEED_KMH)
            return [WalkLeg(time=walk_time)], walk_time

        # find best combination of start/end stops
        starts = []
        ends = []
        dep_times = []
        walk_times = []
        for (s_stop, s_walk), (e_stop, e_walk) in product(start_stops.items(), end_stops.items()):
            starts.append(s_stop)
            ends.append(e_stop)
            dep_times.append(dep_time)
            walk_times.append(s_walk + e_walk)

        route = self.csa.route_many(starts, ends, dep_times, walk_times)
        if not route['path']:
            raise NoTransitRouteFound

        time = route['time']
        route = route['path'][::-1]
        return [
            TransitLeg(
                dep_stop=l['dep_stop'],
                arr_stop=l['arr_stop'],
                dep_time=l['dep_time'],
                arr_time=l['arr_time'],
                trip_id=l['trip_id']) if l['type'] == 1
            else TransferLeg(
                dep_stop=l['dep_stop'],
                arr_stop=l['arr_stop'],
                time=l['time'])
            for l in route], time

    def route_stops(self, start_idx, end_idx, dep_time):
        return self.csa.route(start_idx, end_idx, dep_time)
