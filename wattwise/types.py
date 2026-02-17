"""Type definitions for WattWise configuration and data structures."""

from typing import TypedDict


class HomeAssistantConfig(TypedDict):
    host: str
    token: str
    entity_id: str
    current_entity_id: str


class KasaConfig(TypedDict, total=False):
    device_ip: str
    alias: str
    username: str
    password: str


class DisplayThresholds(TypedDict, total=False):
    warning: int
    critical: int


class DisplayColors(TypedDict, total=False):
    normal: str
    warning: str
    critical: str


class DisplayConfig(TypedDict, total=False):
    thresholds: DisplayThresholds
    colors: DisplayColors


class EnergyConfig(TypedDict, total=False):
    rate: float
    currency_symbol: str


class AlertNotification(TypedDict, total=False):
    type: str
    url: str
    command: str


class AlertConfig(TypedDict, total=False):
    enabled: bool
    threshold: float
    sustained_seconds: int
    notifications: list[AlertNotification]


class DeviceConfig(TypedDict, total=False):
    name: str
    type: str  # "kasa" or "homeassistant"
    # Kasa fields
    device_ip: str
    alias: str
    username: str
    password: str
    # HomeAssistant fields
    host: str
    token: str
    entity_id: str
    current_entity_id: str


class WattWiseConfig(TypedDict, total=False):
    homeassistant: HomeAssistantConfig
    kasa: KasaConfig
    display: DisplayConfig
    energy: EnergyConfig
    alerts: AlertConfig
    devices: list[DeviceConfig]


class TrendData(TypedDict):
    current: float
    min: float
    max: float
    avg: float
    samples: int
    period_minutes: int


class DeviceInfo(TypedDict, total=False):
    model: str
    alias: str
    device_id: str
    has_emeter: bool
    is_on: bool
    current_consumption: float
    voltage: float
    current: float


class DiscoveredDevice(TypedDict):
    index: int
    name: str
    ip: str
    model: str
    has_emeter: bool
    state: bool


DEFAULT_CONFIG: WattWiseConfig = {
    "homeassistant": {
        "host": "",
        "token": "",
        "entity_id": "",
        "current_entity_id": "",
    },
    "kasa": {
        "device_ip": "",
        "alias": "PC",
    },
}
