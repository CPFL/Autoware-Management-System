#!/usr/bin/env python
# coding: utf-8

import json
import uuid
from sys import float_info
from math import modf
from time import time

from ams.helpers import Waypoint, Lane, Location
from ams.structures import ROUTE, Autoware
from ams.structures import Route as Structure
from ams.structures import Routes as Structures


class Route(object):

    CONST = ROUTE

    @classmethod
    def new_route(cls, waypoint_ids, lane_codes, delimiters=None):
        if delimiters is None:
            return Structure.new_data(
                waypoint_ids=waypoint_ids,
                lane_codes=lane_codes
            )
        return Structure.new_data(
            waypoint_ids=waypoint_ids,
            lane_codes=lane_codes,
            delimiters=delimiters
        )

    validate_route = Structure.validate_data
    get_errors = Structure.get_errors

    @classmethod
    def new_point_route(cls, waypoint_id, lane_code):
        return Structure.new_data(
            waypoint_ids=[waypoint_id, waypoint_id],
            lane_codes=[lane_code]
        )

    @classmethod
    def new_point_route_from_location(cls, location):
        return Route.new_point_route(location.waypoint_id, location.lane_code)

    @classmethod
    def new_routes(cls, routes):
        return Structures.new_data(routes)

    @classmethod
    def load(cls, path):
        with open(path, "r") as f:
            data = json.load(f)
            routes = dict(map(lambda x: (x["ID"], x), data["routes"]))
        return routes

    @classmethod
    def get_route_code(cls, route_id, routes):
        return routes[route_id]["code"]

    @classmethod
    def get_route(cls, route_id, routes):
        start_waypoint_id, lane_codes, goal_waypoint_id = \
            cls.get_route_code(route_id, routes).split(ROUTE.DELIMITERS.WAYPOINT_ON_LANE)
        return cls.new_route(
            waypoint_ids=[start_waypoint_id, goal_waypoint_id], lane_codes=lane_codes)

    @classmethod
    def get_route_ids(cls, routes):
        return tuple(routes.keys())

    @classmethod
    def get_route_from_lane_code(cls, lane_code, lanes):
        lane = Lane.get_lane(lane_code, lanes)
        return cls.new_route([lane["waypointIDs"][0], lane["waypointIDs"][-1]], [lane_code])

    @classmethod
    def split_lane_codes(cls, joined_lane_code):
        lane_codes = []
        for joined_foreward_lane_code in joined_lane_code.split(ROUTE.DELIMITERS.BACKWARD):
            waypoint_ids = joined_foreward_lane_code.split(ROUTE.DELIMITERS.FOREWARD)
            for i in range(1, len(waypoint_ids)):
                lane_codes.append(Lane.CONST.DELIMITER.join(waypoint_ids[i-1:i+1]))
        return lane_codes

    @classmethod
    def encode(cls, route):
        if "delimiters" not in route:
            delimiters = [":"] + [">"]*len(route.lane_codes) + [":"]
        else:
            delimiters = route.delimiters

        route_parts = [route.waypoint_ids[0]]
        waypoint_id_index = 1
        lane_code_index = 0
        for i, delimiter in enumerate(delimiters):
            if delimiter == ROUTE.DELIMITERS.WAYPOINT_ON_LANE:
                if i == len(delimiters) - 1 or delimiters[i+1] == ROUTE.DELIMITERS.WAYPOINT_ON_LANE:
                    route_parts.append(route.waypoint_ids[waypoint_id_index])
                    waypoint_id_index += 1
            elif delimiter == ROUTE.DELIMITERS.FOREWARD:
                end_waypoint_ids = Lane.split_lane_code(route.lane_codes[lane_code_index])
                end_waypoint_ids.insert(1, ROUTE.DELIMITERS.FOREWARD)
                if ROUTE.DELIMITERS.FOREWARD+end_waypoint_ids[0] in route_parts[-1]:
                    route_parts[-1] += "".join(end_waypoint_ids[1:])
                else:
                    route_parts.append("".join(end_waypoint_ids))
                lane_code_index += 1
            elif delimiter == ROUTE.DELIMITERS.BACKWARD:
                end_waypoint_ids = Lane.split_lane_code(route.lane_codes[lane_code_index])
                end_waypoint_ids.reverse()
                end_waypoint_ids.insert(1, ROUTE.DELIMITERS.BACKWARD)
                if ROUTE.DELIMITERS.BACKWARD+end_waypoint_ids[0] in route_parts[-1]:
                    route_parts[-1] += "".join(end_waypoint_ids[1:])
                else:
                    route_parts.append("".join(end_waypoint_ids))
                lane_code_index += 1
            else:
                raise ValueError("Unknown delimiter: {}".format(delimiter))

        return ROUTE.DELIMITERS.WAYPOINT_ON_LANE.join(route_parts)

    @classmethod
    def decode(cls, route_code):
        route_parts = route_code.split(ROUTE.DELIMITERS.WAYPOINT_ON_LANE)
        waypoint_ids = []
        lane_codes = []
        delimiters = []
        for i, route_part in enumerate(route_parts):
            if any(map(lambda x: x in route_part, ROUTE.DELIMITERS)):
                if ROUTE.DELIMITERS.FOREWARD in route_part:
                    lane_parts = route_part.split(ROUTE.DELIMITERS.FOREWARD)
                    for j in range(len(lane_parts)-1):
                        end_waypoint_ids = lane_parts[j:j+2]
                        lane_codes.append(Lane.CONST.DELIMITER.join(end_waypoint_ids))
                        delimiters.append(ROUTE.DELIMITERS.FOREWARD)
                elif ROUTE.DELIMITERS.BACKWARD in route_part:
                    lane_parts = route_part.split(ROUTE.DELIMITERS.BACKWARD)
                    for j in range(len(lane_parts)-1):
                        end_waypoint_ids = lane_parts[j:j+2]
                        end_waypoint_ids.reverse()
                        lane_codes.append(Lane.CONST.DELIMITER.join(end_waypoint_ids))
                        delimiters.append(ROUTE.DELIMITERS.BACKWARD)
                else:
                    raise ValueError("Unknown route_part discription: {}".format(route_part))
            else:
                waypoint_ids.append(route_part)
            if i < len(route_parts) - 1:
                delimiters.append(ROUTE.DELIMITERS.WAYPOINT_ON_LANE)

        return Route.new_route(waypoint_ids, lane_codes, delimiters)

    @classmethod
    def get_routes_divided_by_action(cls, route):
        routes = [{
            "waypoint_ids": [route.waypoint_ids[0]],
            "lane_codes": [],
            "delimiters": [ROUTE.DELIMITERS.WAYPOINT_ON_LANE]
        }]
        waypoint_ids_index = 1
        lane_codes_index = 0
        delimiters_index = 1
        while delimiters_index < len(route.delimiters):
            if ROUTE.DELIMITERS.WAYPOINT_ON_LANE == route.delimiters[delimiters_index]:
                routes[-1]["waypoint_ids"].append(route.waypoint_ids[waypoint_ids_index])
                routes[-1]["delimiters"].append(route.delimiters[delimiters_index])
                delimiters_index += 1
                if delimiters_index == len(route.delimiters):
                    break
                routes.append({
                    "waypoint_ids": [route.waypoint_ids[waypoint_ids_index]],
                    "lane_codes": [],
                    "delimiters": [route.delimiters[delimiters_index]]
                })
                waypoint_ids_index += 1
                delimiters_index += 1
            else:
                routes[-1]["lane_codes"].append(route.lane_codes[lane_codes_index])
                lane_codes_index += 1
                routes[-1]["delimiters"].append(route.delimiters[delimiters_index])
                delimiters_index += 1
        return Structures.new_data(routes)

    @classmethod
    def __update_lane_waypoint_ids_with_both_endpoints(cls, i, lane_waypoint_ids, route):
        if i == 0:
            index = lane_waypoint_ids.index(route.waypoint_ids[0])
            if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                index = lane_waypoint_ids.index(route.waypoint_ids[1])
            lane_waypoint_ids = lane_waypoint_ids[index:]

        if i == len(route.lane_codes) - 1:
            index = lane_waypoint_ids.index(route.waypoint_ids[1])
            if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                index = lane_waypoint_ids.index(route.waypoint_ids[0])
            lane_waypoint_ids = lane_waypoint_ids[:index + 1]
        return lane_waypoint_ids

    @classmethod
    def get_waypoint_ids(cls, route_code, lanes):
        routes = cls.get_routes_divided_by_action(cls.decode(route_code))
        waypoint_ids = []
        for route in routes:
            for i, lane_code in enumerate(route.lane_codes):
                lane_waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
                lane_waypoint_ids = cls.__update_lane_waypoint_ids_with_both_endpoints(i, lane_waypoint_ids, route)

                if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                    lane_waypoint_ids.reverse()

                if 0 < len(waypoint_ids):
                    waypoint_ids = waypoint_ids[:-1]

                waypoint_ids.extend(lane_waypoint_ids)

        return waypoint_ids

    @classmethod
    def get_route_point_pose_and_location(cls, route_point, lanes, waypoints):
        if 0 <= route_point.index:
            routes = cls.get_routes_divided_by_action(cls.decode(route_point.route_code))
            m = 0
            for route in routes:
                for i, lane_code in enumerate(route.lane_codes):
                    lane_waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
                    lane_waypoint_ids = cls.__update_lane_waypoint_ids_with_both_endpoints(
                        i, lane_waypoint_ids, route)

                    if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                        lane_waypoint_ids.reverse()

                    m = 0 if m == 0 else m - 1

                    if route_point.index < m + len(lane_waypoint_ids):
                        return Lane.get_pose(lane_code, lane_waypoint_ids[route_point.index-m], lanes, waypoints),\
                            Location.new_location(lane_waypoint_ids[route_point.index-m], lane_code)
                    else:
                        m += len(lane_waypoint_ids)
        return None, None

    @classmethod
    def generate_lane_code_waypoint_id_relations(cls, route_code, lanes):
        routes = cls.get_routes_divided_by_action(cls.decode(route_code))
        lane_code_waypoint_id_relations = []
        for route in routes:
            for i, lane_code in enumerate(route.lane_codes):
                lane_waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
                lane_waypoint_ids = cls.__update_lane_waypoint_ids_with_both_endpoints(
                    i, lane_waypoint_ids, route)

                direction = ROUTE.DELIMITERS.FOREWARD
                if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                    lane_waypoint_ids.reverse()
                    direction = ROUTE.DELIMITERS.BACKWARD

                lane_code_waypoint_id_relations.append({
                    "lane_code": lane_code,
                    "waypoint_ids": lane_waypoint_ids,
                    "direction": direction
                })
        return lane_code_waypoint_id_relations

    @classmethod
    def get_pose_and_velocity_set(cls, route_code, lanes, waypoints):
        routes = cls.get_routes_divided_by_action(cls.decode(route_code))
        pose_and_velocity_set = []
        for route in routes:
            for i, lane_code in enumerate(route.lane_codes):
                lane_waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
                lane_waypoint_ids = cls.__update_lane_waypoint_ids_with_both_endpoints(
                    i, lane_waypoint_ids, route)

                if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                    lane_waypoint_ids.reverse()

                if 0 < len(pose_and_velocity_set):
                    pose_and_velocity_set = pose_and_velocity_set[:-1]

                for waypoint_id in lane_waypoint_ids:
                    velocity = Waypoint.get_velocity(waypoint_id, waypoints)
                    pose = Lane.get_pose(lane_code, waypoint_id, lanes, waypoints)
                    if ROUTE.DELIMITERS.BACKWARD in route.delimiters:
                        velocity = -velocity
                    pose_and_velocity_set.append([pose, velocity])
        return pose_and_velocity_set

    @classmethod
    def generate_lane_array(cls, route_code, lanes, waypoints, current_time=None):
        pose_and_velocity_set = Route.get_pose_and_velocity_set(route_code, lanes, waypoints)

        header = Autoware.ROSMessage.Header.get_template()
        if current_time is None:
            current_time = time()
        nsec, sec = modf(current_time)
        header.stamp.secs = int(sec)
        header.stamp.nsecs = int(nsec * (10 ** 9))
    
        lane_array = Autoware.ROSMessage.LaneArray.get_template()
        lane_array.id = int(uuid.uuid4().int & (1 << 31)-1)
        lane_array.lanes[0].header = header
        lane_array.lanes[0].waypoints = []
    
        for pose, velocity in pose_and_velocity_set:
            waypoint = Autoware.ROSMessage.LaneArray.Lane.Waypoint.get_template()
            waypoint.pose.header = header
            waypoint.pose.pose.position.x = pose.position.x
            waypoint.pose.pose.position.y = pose.position.y
            waypoint.pose.pose.position.z = pose.position.z
            waypoint.pose.pose.orientation.z = pose.orientation.quaternion.z
            waypoint.pose.pose.orientation.w = pose.orientation.quaternion.w
    
            waypoint.twist.header = header
            waypoint.twist.twist.linear.x = velocity

            lane_array.lanes[0].waypoints.append(waypoint)
    
        return lane_array

    @classmethod
    def get_length(cls, route, lanes, waypoints):
        lane_codes = route.lane_codes
        start_waypoint_id = route.waypoint_ids[0]
        goal_waypoint_id = route.waypoint_ids[-1]
        length = 0.0
        for i, lane_code in enumerate(lane_codes):
            waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
            js = 0
            if i == 0 and start_waypoint_id in waypoint_ids:
                js = waypoint_ids.index(start_waypoint_id)
            je = len(waypoint_ids)
            if i == len(lane_codes)-1 and goal_waypoint_id in waypoint_ids:
                je = waypoint_ids.index(goal_waypoint_id) + 1

            if js == 0 and je == len(waypoint_ids):
                length += Lane.get_length(lane_code, lanes)
            else:
                for j in range(js+1, je):
                    length += Lane.get_distance(
                        Waypoint.get_position(waypoint_ids[j - 1], waypoints),
                        Waypoint.get_position(waypoint_ids[j], waypoints))
        return length

    @classmethod
    def __get_goal_lane_candidates(cls, goals, reverse, lanes, waypoints, cost_function):
        goal_lane_candidates = {}
        for goal in goals:
            goal_id = goal["goal_id"]
            lane_code = goal["lane_code"]
            if reverse:
                end_waypoint_id = Lane.get_waypoint_ids(lane_code, lanes)[-1]
            else:
                end_waypoint_id = Lane.get_waypoint_ids(lane_code, lanes)[0]
            cost = cost_function(
                cls.new_route([end_waypoint_id, goal["waypoint_id"]], [lane_code]), lanes, waypoints)

            goal_points = goal_lane_candidates.get(lane_code, {})
            goal_points[goal_id] = {
                "lane_code": lane_code,
                "goal_id": goal_id,
                "waypoint_id": goal["waypoint_id"],
                "cost": cost,
            }
            goal_lane_candidates[lane_code] = goal_points

        return goal_lane_candidates

    @classmethod
    def __is_directly_reach(cls, lane_code, start_waypoint_id, goal_waypoint_id, reverse, lanes):
        waypoint_ids = Lane.get_waypoint_ids(lane_code, lanes)
        is_directly_reach = waypoint_ids.index(start_waypoint_id) <= waypoint_ids.index(goal_waypoint_id)
        return is_directly_reach if not reverse else not is_directly_reach

    @classmethod
    def get_shortest_routes(
            cls, start, goals, lanes, to_lanes, from_lanes, waypoints, cost_function,
            cost_limit=ROUTE.COST_LIMIT, reverse=False):
        """
        # Dijkstra's algorithm
        """
        next_lanes = to_lanes
        local_start_waypoint_id = start["waypoint_id"]
        local_goal_waypoint_id = Lane.get_waypoint_ids(start["lane_code"], lanes)[-1]
        if reverse:
            next_lanes = from_lanes
            local_start_waypoint_id = Lane.get_waypoint_ids(start["lane_code"], lanes)[0]
            local_goal_waypoint_id = start["waypoint_id"]

        local_route = cls.new_route([local_start_waypoint_id, local_goal_waypoint_id], [start["lane_code"]])
        cost_start_to_end = cost_function(local_route, lanes, waypoints)

        goal_lane_candidates = cls.__get_goal_lane_candidates(goals, reverse, lanes, waypoints, cost_function)

        checked_lane_code = []
        current_lane_code = start["lane_code"]

        end_lanes = {current_lane_code: {"cost": cost_start_to_end, "prev_lanes": []}}
        shortest_routes = {}

        for goal_points in goal_lane_candidates.values():
            for goal_candidate in goal_points.values():
                if start["lane_code"] == goal_candidate["lane_code"]:
                    if cls.__is_directly_reach(
                            start["lane_code"], start["waypoint_id"], goal_candidate["waypoint_id"], reverse, lanes):
                        local_start_waypoint_id = start["waypoint_id"]
                        local_goal_waypoint_id = goal_candidate["waypoint_id"]
                        if reverse:
                            local_start_waypoint_id = goal_candidate["waypoint_id"]
                            local_goal_waypoint_id = start["waypoint_id"]
                        cost_start_to_goal = cost_function(
                            cls.new_route([local_start_waypoint_id, local_goal_waypoint_id], [start["lane_code"]]),
                            lanes, waypoints)
                        shortest_routes[goal_candidate["goal_id"]] = cls.new_route(
                            [start["waypoint_id"], goal_candidate["waypoint_id"]], [start["lane_code"]])
                        shortest_routes[goal_candidate["goal_id"]].update({
                            "goal_id": goal_candidate["goal_id"],
                            "cost": cost_start_to_goal
                        })

        while True:
            next_lane_codes = next_lanes[current_lane_code]

            if 0 == len(next_lane_codes):
                end_lanes[current_lane_code]["cost"] = float_info.max

                end_lanes_filtered = dict(filter(lambda x: x[1]["cost"] < cost_limit, end_lanes.items()))
                if len(end_lanes_filtered) == 0:
                    break
                current_lane_code = min(end_lanes_filtered.items(), key=lambda x: x[1]["cost"])[0]

                continue

            for next_lane_id in next_lane_codes:
                if next_lane_id in checked_lane_code and next_lane_id != start["lane_code"]:
                    continue
                if next_lane_id in end_lanes:
                    continue

                end_lanes[next_lane_id] = {
                    "cost": end_lanes[current_lane_code]["cost"] + cost_function(
                        Route.get_route_from_lane_code(current_lane_code, lanes), lanes, waypoints),
                    "prev_lanes": [current_lane_code] + end_lanes[current_lane_code]["prev_lanes"]
                }

                for goal_candidate in goal_lane_candidates.get(next_lane_id, {}).values():
                    if end_lanes[next_lane_id]["cost"] + goal_candidate["cost"] < cost_limit:
                        shortest_route = cls.new_route(
                            [start["waypoint_id"], goal_candidate["waypoint_id"]],
                            [next_lane_id] + end_lanes[next_lane_id]["prev_lanes"])
                        shortest_route.update({
                            "goal_id": goal_candidate["goal_id"],
                            "cost": end_lanes[next_lane_id]["cost"] + goal_candidate["cost"],
                        })
                        shortest_routes[goal_candidate["goal_id"]] = shortest_route

            end_lanes.pop(current_lane_code)
            checked_lane_code.append(current_lane_code)

            if len(shortest_routes) == len(goal_lane_candidates):
                break

            end_lanes_filtered = dict(filter(lambda x: x[1]["cost"] < cost_limit, end_lanes.items()))
            if len(end_lanes_filtered) == 0:
                break
            current_lane_code = min(end_lanes_filtered.items(), key=lambda x: x[1]["cost"])[0]

        if reverse:
            for route_id in shortest_routes:
                shortest_routes[route_id]["start_waypoint_id"] = shortest_routes[route_id]["goal_waypoint_id"]
                shortest_routes[route_id]["goal_waypoint_id"] = start["waypoint_id"]
        else:
            for route_id in shortest_routes:
                shortest_routes[route_id]["lane_codes"].reverse()

        return shortest_routes
