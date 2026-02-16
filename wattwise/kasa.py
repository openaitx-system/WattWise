"""
Module for interacting with TP-Link Kasa and Tapo smart plugs.

Uses the modern python-kasa 0.10+ API with Module-based feature detection
and auto-detection of device type (IoT/SMART/Tapo).
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.table import Table

from . import config

console = Console()
logger = logging.getLogger(__name__)

try:
    from kasa import Credentials, Discover, Module
    from kasa.device import Device

    KASA_AVAILABLE = True
except ImportError:
    KASA_AVAILABLE = False
    logger.warning(
        "python-kasa library not found. "
        "Install with 'pip install python-kasa' to use Kasa devices."
    )


class KasaError(Exception):
    """Exception raised for Kasa device errors."""

    pass


class KasaDevice:
    """Client for TP-Link Kasa and Tapo smart plugs.

    Uses modern python-kasa 0.10+ APIs with Module-based feature detection.
    Supports legacy Kasa (IoT), SMART, and Tapo device protocols automatically.
    """

    def __init__(
        self,
        device_ip: str,
        alias: str = "",
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        if not KASA_AVAILABLE:
            raise ImportError(
                "python-kasa library not installed. "
                "Run 'pip install python-kasa' to use Kasa devices."
            )

        self.device_ip = device_ip
        self.alias = alias
        self.username = username
        self.password = password
        self.device: Device | None = None
        self.history: list[tuple[float, float]] = []
        self.current_history: list[tuple[float, float]] = []
        self.max_history_size = 100

        self._load_history_from_file()

    def _load_history_from_file(self) -> None:
        """Load historical data from file if available."""
        history_file = os.path.join(config.get_data_dir(), "history.json")

        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history_data = json.load(f)
                    power_history = history_data.get("power", [])

                    if power_history and not self.history:
                        self.history = power_history

                    logger.info(
                        f"Loaded {len(self.history)} power readings from history"
                    )
            except Exception as e:
                logger.warning(f"Could not load history from file: {e}")

    async def _connect(self) -> tuple[bool, str | None]:
        """Connect to the device using auto-detection."""
        try:
            kwargs: dict[str, Any] = {"timeout": 10}
            if self.username and self.password:
                kwargs["username"] = self.username
                kwargs["password"] = self.password

            self.device = await Discover.discover_single(
                self.device_ip, **kwargs
            )
            await self.device.update()
            return True, None
        except TimeoutError:
            error_msg = (
                f"Connection to {self.device_ip} timed out after 10 seconds"
            )
            logger.error(error_msg)
            return False, error_msg
        except ConnectionRefusedError:
            error_msg = f"Connection refused by device at {self.device_ip}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            logger.error(
                f"Failed to connect to Kasa device at {self.device_ip}: {e}"
            )
            return False, str(e)

    def validate_connection(self) -> tuple[bool, str | None]:
        """Validate connection to the Kasa device (sync wrapper)."""
        return asyncio.run(self._connect())

    def _get_energy_module(self) -> Any | None:
        """Get the Energy module from the device, if available."""
        if self.device is None:
            return None
        return self.device.modules.get(Module.Energy)

    async def _update_device(self) -> None:
        """Update device state."""
        if self.device is not None:
            await self.device.update()

    def get_power_usage(self) -> float | None:
        """Get current power usage in watts.

        Matches the HomeAssistant interface for unified DataSource usage.
        """
        try:
            if self.device is None:
                success, error = self.validate_connection()
                if not success:
                    logger.error(f"Cannot get power: {error}")
                    return None

            asyncio.run(self._update_device())
            energy = self._get_energy_module()

            if not energy:
                logger.warning(
                    f"Device {self.device_ip} does not support energy monitoring"
                )
                return None

            watts = energy.current_consumption
            if watts is not None:
                timestamp = time.time()
                self.history.append((timestamp, watts))

                if len(self.history) > self.max_history_size:
                    self.history = self.history[-self.max_history_size :]

                return float(watts)
            return None
        except Exception as e:
            logger.error(f"Failed to get power usage from Kasa device: {e}")
            return None

    def get_current_amperage(self) -> float | None:
        """Get current amperage from the device."""
        try:
            if self.device is None:
                success, error = self.validate_connection()
                if not success:
                    logger.error(f"Cannot get current: {error}")
                    return None

            asyncio.run(self._update_device())
            energy = self._get_energy_module()
            if energy is None:
                return None
            current = energy.current
            if current is not None:
                timestamp = time.time()
                self.current_history.append((timestamp, current))
                if len(self.current_history) > self.max_history_size:
                    self.current_history = self.current_history[
                        -self.max_history_size :
                    ]
                return float(current)
            return None
        except Exception as e:
            logger.error(f"Failed to get current amperage: {e}")
            return None

    def get_voltage(self) -> float | None:
        """Get voltage from the device."""
        try:
            energy = self._get_energy_module()
            if energy is None:
                return None
            voltage = energy.voltage
            return float(voltage) if voltage is not None else None
        except Exception as e:
            logger.error(f"Failed to get voltage: {e}")
            return None

    def get_consumption_today(self) -> float | None:
        """Get today's energy consumption in kWh from the device."""
        try:
            energy = self._get_energy_module()
            if energy is None:
                return None
            consumption = energy.consumption_today
            return float(consumption) if consumption is not None else None
        except Exception as e:
            logger.error(f"Failed to get today's consumption: {e}")
            return None

    def get_device_info(self) -> dict[str, Any]:
        """Get device information including model, alias, and energy data."""
        try:
            if self.device is None:
                success, error = self.validate_connection()
                if not success:
                    return self._empty_device_info()

            asyncio.run(self._update_device())

            info: dict[str, Any] = {
                "model": getattr(self.device, "model", "Unknown"),
                "alias": getattr(self.device, "alias", self.alias or "Unknown"),
                "device_id": getattr(self.device, "device_id", "Unknown"),
                "has_emeter": getattr(self.device, "has_emeter", False),
                "is_on": getattr(self.device, "is_on", False),
            }

            energy = self._get_energy_module()
            if energy:
                info.update(
                    {
                        "current_consumption": energy.current_consumption,
                        "voltage": getattr(energy, "voltage", 0),
                        "current": getattr(energy, "current", 0),
                    }
                )
            else:
                info.update(
                    {"current_consumption": 0, "voltage": 0, "current": 0}
                )

            return info
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            return self._empty_device_info()

    def _empty_device_info(self) -> dict[str, Any]:
        """Return empty device info for error cases."""
        return {
            "model": "Unknown",
            "alias": self.alias or "Unknown",
            "device_id": "Unknown",
            "has_emeter": False,
            "is_on": False,
            "current_consumption": 0,
            "voltage": 0,
            "current": 0,
        }

    def get_power_trend(
        self, minutes: int = 5
    ) -> dict[str, Any] | None:
        """Get power usage trend data for the past X minutes."""
        if not self.history:
            return None

        now = time.time()
        cutoff = now - (minutes * 60)

        relevant_history = [
            (t, p) for t, p in self.history if t >= cutoff
        ]

        if len(relevant_history) < 2:
            return None

        values = [p for _, p in relevant_history]

        return {
            "current": values[-1],
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "samples": len(values),
            "period_minutes": minutes,
        }

    def get_current_trend(
        self, minutes: int = 5
    ) -> dict[str, Any] | None:
        """Get current amperage trend data for the past X minutes."""
        if not self.current_history:
            return None

        now = time.time()
        cutoff = now - (minutes * 60)

        relevant_history = [
            (t, c) for t, c in self.current_history if t >= cutoff
        ]

        if len(relevant_history) < 2:
            return None

        values = [c for _, c in relevant_history]

        return {
            "current": values[-1],
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "samples": len(values),
            "period_minutes": minutes,
        }


async def discover_devices(
    timeout: int = 5,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Discover Kasa/Tapo devices on the network.

    Supports authenticated discovery for SMART/Tapo devices.
    """
    if not KASA_AVAILABLE:
        raise ImportError(
            "python-kasa library not installed. "
            "Run 'pip install python-kasa' to use Kasa devices."
        )

    try:
        console.print(
            f"Discovering Kasa devices on your network for {timeout} seconds..."
        )
        kwargs: dict[str, Any] = {"discovery_timeout": timeout}
        if username and password:
            kwargs["credentials"] = Credentials(username, password)

        devices = await Discover.discover(**kwargs)
        return devices
    except Exception as e:
        logger.error(f"Error discovering devices: {e}")
        return {}


def display_discovered_devices(
    devices: dict[str, Any],
) -> list[dict[str, Any]]:
    """Display discovered devices in a table and return device info list."""
    if not devices:
        console.print(
            "[yellow]No Kasa devices found on your network.[/yellow]"
        )
        console.print(
            "Make sure your devices are powered on and connected to the same network."
        )
        return []

    table = Table(title="Discovered Kasa Devices")
    table.add_column("#", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("IP Address", style="blue")
    table.add_column("Model", style="magenta")
    table.add_column("Power", style="yellow")
    table.add_column("State", style="red")

    device_list: list[dict[str, Any]] = []
    index = 1

    for ip, device in devices.items():
        name = getattr(device, "alias", "Unknown")
        model = getattr(device, "model", "Unknown")
        state = getattr(device, "is_on", False)
        state_display = "[green]ON[/green]" if state else "[red]OFF[/red]"
        power = "N/A"

        has_emeter = getattr(device, "has_emeter", False)

        if has_emeter:
            try:
                energy = device.modules.get(Module.Energy)
                if energy:
                    watts = energy.current_consumption
                    power = f"{watts:.1f} W"
            except Exception as e:
                logger.debug(
                    f"Error getting power consumption for {name}: {e}"
                )
                power = "Error"

        table.add_row(
            str(index),
            name or "Unknown",
            ip,
            model or "Unknown",
            power,
            state_display,
        )

        device_list.append(
            {
                "index": index,
                "name": name,
                "ip": ip,
                "model": model,
                "has_emeter": has_emeter,
                "state": state,
            }
        )

        index += 1

    console.print(table)
    console.print(
        f"Found {len(device_list)} Kasa devices on your network.\n"
    )

    return device_list


def discover_devices_sync(
    timeout: int = 5,
    display: bool = True,
    username: str | None = None,
    password: str | None = None,
) -> list[dict[str, Any]]:
    """Synchronous wrapper for device discovery."""
    if not KASA_AVAILABLE:
        logger.warning(
            "python-kasa library not installed. "
            "Run 'pip install python-kasa' to use Kasa devices."
        )
        return []

    try:
        devices = asyncio.run(discover_devices(timeout, username, password))

        if display:
            return display_discovered_devices(devices)

        device_list: list[dict[str, Any]] = []
        index = 1

        for ip, device in devices.items():
            name = getattr(device, "alias", "Unknown")
            model = getattr(device, "model", "Unknown")
            state = getattr(device, "is_on", False)
            has_emeter = getattr(device, "has_emeter", False)

            device_list.append(
                {
                    "index": index,
                    "name": name,
                    "ip": ip,
                    "model": model,
                    "has_emeter": has_emeter,
                    "state": state,
                }
            )

            index += 1

        return device_list
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        return []
