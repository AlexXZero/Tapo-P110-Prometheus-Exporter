from contextlib import contextmanager
from enum import Enum, auto
from math import floor
from time import time

from loguru import logger
import prometheus_client as prometheus
from prometheus_client.core import GaugeMetricFamily
from PyP100 import PyP110
from base64 import b64decode


class MetricType(Enum):
    DEVICE_COUNT = auto()
    TODAY_RUNTIME = auto()
    MONTH_RUNTIME = auto()
    TODAY_ENERGY = auto()
    MONTH_ENERGY = auto()
    CURRENT_POWER = auto()
    RSSI = auto()


def get_metrics():
    return {
        MetricType.DEVICE_COUNT: GaugeMetricFamily(
            "tapo_p110_device_count",
            "Number of available TP-Link TAPO P110 Smart Sockets.",
        ),
        MetricType.TODAY_RUNTIME: GaugeMetricFamily(
            "tapo_p110_today_runtime_mins",
            "Current running time for the TP-Link TAPO P110 Smart Socket today. (minutes)",
            labels=["alias", "id", "ip_address", "room"],
        ),
        MetricType.MONTH_RUNTIME: GaugeMetricFamily(
            "tapo_p110_month_runtime_mins",
            "Current running time for the TP-Link TAPO P110 Smart Socket this month. (minutes)",
            labels=["alias", "id", "ip_address", "room"],
        ),
        MetricType.TODAY_ENERGY: GaugeMetricFamily(
            "tapo_p110_today_energy_wh",
            "Energy consumed by the TP-Link TAPO P110 Smart Socket today. (Watt-hours)",
            labels=["alias", "id", "ip_address", "room"],
        ),
        MetricType.MONTH_ENERGY: GaugeMetricFamily(
            "tapo_p110_month_energy_wh",
            "Energy consumed by the TP-Link TAPO P110 Smart Socket this month. (Watt-hours)",
            labels=["alias", "id", "ip_address", "room"],
        ),
        MetricType.CURRENT_POWER: GaugeMetricFamily(
            "tapo_p110_power_consumption_w",
            "Current power consumption for TP-Link TAPO P110 Smart Socket. (Watts)",
            labels=["alias", "id", "ip_address", "room"],
        ),
        MetricType.RSSI: GaugeMetricFamily(
            "tapo_p110_rssi_db",
            "Wifi received signal strength indicator for the TP-Link TAPO P110 Smart Socket. (Decibels)",
            labels=["alias", "id", "ip_address", "room"],
        ),
    }


class Collector:
    def __init__(self, deviceMap, email_address, password):
        def create_device(ip_address, room):
            extra = {
                "ip": ip_address, "room": room,
            }

            logger.debug("connecting to device", extra=extra)
            d = PyP110.P110(ip_address, email_address, password)
            #d.handshake()  # Deprecated
            #d.login()      # Deprecated

            logger.debug("successfully authenticated with device", extra=extra)
            return d

        self.devices = {
            room: (ip_address, create_device(ip_address, room))
            for room, ip_address in deviceMap.items()
        }

        # Stop scraping of default metric
        prometheus.REGISTRY.unregister(prometheus.PROCESS_COLLECTOR)
        prometheus.REGISTRY.unregister(prometheus.PLATFORM_COLLECTOR)
        prometheus.REGISTRY.unregister(prometheus.GC_COLLECTOR)

    def get_device_data(self, device, ip_address, room):
        def get_data():
            info = device.getDeviceInfo()
            energyUsage = device.getEnergyUsage()
            info["nickname"] = b64decode(info["nickname"]).decode("utf-8")
            return {**info, **energyUsage}

        extra = {
            "ip": ip_address, "room": room,
        }
        logger.debug("retrieving energy usage statistics for device", extra=extra)
        try:
            return get_data()
        except Exception as e:
            logger.warning("Connection error. Attempting to reconnect.", extra=extra)
            try:
                device.protocol = None  # Reset connection by clearing protocol field
                return get_data()
            except Exception as re:
                logger.error("Failed to reconnect. Error: {}".format(re), extra=extra)
                raise  # Re-raise the exception if reconnection fails

    def collect(self):
        logger.info("receiving prometheus metrics scrape: collecting observations")

        metrics = get_metrics()
        metrics[MetricType.DEVICE_COUNT].add_metric([], len(self.devices))

        for room, (ip_addr, device) in self.devices.items():
            logger.info("performing observations for device", extra={
                "ip": ip_addr, "room": room,
            })

            try:
                data = self.get_device_data(device, ip_addr, room)

                labels = [data['nickname'], data['device_id'], ip_addr, room]
                metrics[MetricType.TODAY_RUNTIME].add_metric(labels, data['today_runtime'])
                metrics[MetricType.MONTH_RUNTIME].add_metric(labels, data['month_runtime'])
                metrics[MetricType.TODAY_ENERGY].add_metric(labels, data['today_energy'])
                metrics[MetricType.MONTH_ENERGY].add_metric(labels, data['month_energy'])
                metrics[MetricType.CURRENT_POWER].add_metric(labels, data['current_power'])
                metrics[MetricType.RSSI].add_metric(labels, data['rssi'])
            except Exception as e:
                logger.exception("encountered exception during observation!")

        for m in metrics.values():
            yield m
