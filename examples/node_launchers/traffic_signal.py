#!/usr/bin/env python
# coding: utf-8

import json
from time import sleep
from argparse import ArgumentParser
from multiprocessing import Process
from uuid import uuid1 as uuid

import paho.mqtt.client as mqtt

from ams.helpers import Topic, Target
from ams.nodes import TrafficSignal


class MQTTClient(object):
    def __init__(self, host, port):
        self.__client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.__client.connect(host, port=port, keepalive=60)

    def __del__(self):
        self.__client.disconnect()

    def publish(self, topic, message):
        self.__client.publish(topic, message)


parser = ArgumentParser()
parser.add_argument("-H", "--host", type=str, default="localhost", help="host")
parser.add_argument("-P", "--port", type=int, default=1883, help="port")
parser.add_argument("-ID", "--id", type=str, default=None, help="node id")
parser.add_argument("-RC", "--route_code", type=str, required=True, help="route_code")
parser.add_argument("-C", "--cycle", type=str,
                    default=None, help="cycle (json string)")
parser.add_argument("-S", "--schedules", type=str,
                    default=None, help="schedules")
args = parser.parse_args()


if __name__ == '__main__':

    mqtt_client = MQTTClient(args.host, args.port)

    traffic_signal = TrafficSignal(
        _id=args.id if args.id is not None else str(uuid()),
        route_code=args.route_code
    )
    process = Process(target=traffic_signal.start, args=[args.host, args.port])
    process.start()

    if args.cycle is not None:
        sleep(5)
        # print("publish cycles")
        topic = Topic.get_topic(
            from_target=Target.new_target("TrafficSignalCycleSetter", None),
            to_target=traffic_signal.target,
            categories=TrafficSignal.CONST.TOPIC.CATEGORIES.CYCLE,
        )
        mqtt_client.publish(topic, Topic.serialize(json.loads(args.cycle)))

    if args.schedules is not None:
        sleep(5)
        # print("publish schedules")
        topic = Topic.get_topic(
            from_target=Target.new_target("TrafficSignalSchedulesSetter", None),
            to_target=traffic_signal.target,
            categories=TrafficSignal.CONST.TOPIC.CATEGORIES.SCHEDULES
        )
        mqtt_client.publish(topic, Topic.serialize(json.loads(args.schedules)))

    # print("wait join")
    process.join()
