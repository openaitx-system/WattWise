import json
import logging
import os
import sys
from typing import Any, Optional

import typer  # type: ignore[import-not-found]
from rich.console import Console  # type: ignore[import-not-found]
from rich.prompt import Confirm, Prompt  # type: ignore[import-not-found]

from . import config, display, homeassistant
from .alerts import AlertManager
from .cost import estimate_costs
from .datasource import CurrentCapable
from .export import export_history

logger = logging.getLogger("wattwise")

app = typer.Typer(
    name="wattwise",
    help="Monitor power usage from smart plugs using Home Assistant or python-kasa",
    add_completion=False,
)


config_app = typer.Typer(
    help="Configuration commands for data sources",
    add_completion=False,
)
app.add_typer(config_app, name="config")

devices_app = typer.Typer(
    help="Manage monitored devices",
    add_completion=False,
)
app.add_typer(devices_app, name="devices")

console = Console()


def _setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on verbosity flags.

    Default level is WARNING. Use -v for INFO, -q for ERROR.
    """
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
        force=True,
    )


def _get_data_dir() -> str:
    """Get the data directory path, ensuring it exists."""
    data_dir = config.get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _get_history_file() -> str:
    """Get the history file path."""
    return os.path.join(_get_data_dir(), "history.json")


def _get_version() -> str:
    """Get the package version."""
    from . import get_version

    return get_version()


@config_app.command("show")
def show_config() -> None:
    """Show current configuration."""
    try:
        cfg = config.load_config()
        display_mgr = display.DisplayManager(cfg)

        ha_config = cfg["homeassistant"]
        token_display = "Not configured"
        if ha_config["token"]:
            token = ha_config["token"]
            if len(token) > 8:
                token_display = f"{token[:4]}...{token[-4:]}"
            else:
                token_display = "****"

        ha_stats = {
            "host": ha_config["host"],
            "entity_id": f"Power: {ha_config.get('entity_id', 'Not configured')}",
            "current_entity_id": (
                f"Current: {ha_config.get('current_entity_id', 'Not configured')}"
            ),
            "token": token_display,
        }
        display_mgr.display_stats("Home Assistant Configuration", ha_stats)

        kasa_config = cfg["kasa"]
        kasa_stats = {
            "device_ip": kasa_config.get("device_ip", "Not configured"),
            "alias": kasa_config.get("alias", "Not configured"),
        }
        display_mgr.display_stats("Kasa Device Configuration", kasa_stats)

        display_mgr.display_stats(
            "Configuration Info",
            {
                "config_file": config.get_config_path(),
                "data_dir": _get_data_dir(),
                "version": _get_version(),
            },
        )
    except config.ConfigError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@config_app.command("ha")
def configure_ha() -> None:
    """Configure Home Assistant integration."""
    try:
        cfg = config.load_config()
        display_mgr = display.DisplayManager(cfg)

        console.print("[bold blue]WattWise - Home Assistant Configuration[/bold blue]")

        cfg["homeassistant"]["host"] = Prompt.ask(
            "Home Assistant host", default=cfg["homeassistant"]["host"]
        )

        current_token = cfg["homeassistant"]["token"]
        token_prompt = "Home Assistant Long-Lived Access Token"
        if current_token:
            token_prompt += " (current token set, leave empty to keep)"

        new_token = Prompt.ask(token_prompt, default="", password=True)

        if new_token:
            cfg["homeassistant"]["token"] = new_token

        device_name = Prompt.ask(
            "Device name (e.g. epyc_workstation)",
            default=cfg["homeassistant"].get("device_name", "epyc_workstation"),
        )
        cfg["homeassistant"]["device_name"] = device_name

        power_entity_id = f"sensor.{device_name}_current_consumption"
        current_entity_id = f"sensor.{device_name}_current"

        console.print(f"[dim]Using power sensor: [cyan]{power_entity_id}[/cyan][/dim]")
        console.print(
            f"[dim]Using current sensor: [cyan]{current_entity_id}[/cyan][/dim]"
        )

        if Confirm.ask("Customize sensor entity IDs?", default=False):
            power_entity_id = Prompt.ask(
                "Power consumption entity ID", default=power_entity_id
            )
            current_entity_id = Prompt.ask(
                "Current amperage entity ID", default=current_entity_id
            )

        cfg["homeassistant"]["entity_id"] = power_entity_id
        cfg["homeassistant"]["current_entity_id"] = current_entity_id

        if cfg["homeassistant"]["host"] and cfg["homeassistant"]["token"]:
            console.print("Testing Home Assistant connection...")
            ha_client = homeassistant.HomeAssistant(
                cfg["homeassistant"]["host"],
                cfg["homeassistant"]["token"],
                cfg["homeassistant"]["entity_id"],
                current_entity_id=cfg["homeassistant"]["current_entity_id"],
            )

            success, error = ha_client.validate_connection()
            if success:
                display_mgr.show_success("Home Assistant", "Connection successful!")
            else:
                display_mgr.show_error("Home Assistant", f"Connection failed: {error}")
        else:
            console.print(
                "[yellow]Note: Both Home Assistant host "
                "and token are required.[/yellow]"
            )

        config.save_config(cfg)
        display_mgr.show_success(
            "Configuration", "Home Assistant settings saved successfully!"
        )

        console.print("\n[bold]Next steps:[/bold]")
        console.print(
            "- Run [bold cyan]wattwise[/bold cyan] to see current power usage"
        )
        console.print(
            "- Run [bold cyan]wattwise --current[/bold cyan] "
            "to see both power and current"
        )
        console.print(
            "- Run [bold cyan]wattwise --watch[/bold cyan] "
            "to continuously monitor power usage"
        )

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@config_app.command("kasa")
def configure_kasa() -> None:
    """Configure Kasa smart plug integration."""
    try:
        from . import kasa

        cfg = config.load_config()
        display_mgr = display.DisplayManager(cfg)

        console.print("[bold blue]WattWise - Kasa Smart Plug Configuration[/bold blue]")

        console.print("\n[bold]Discovering Kasa devices on your network...[/bold]")
        discovered_devices = kasa.discover_devices_sync(timeout=8)

        device_ip = ""
        device_alias = ""

        if discovered_devices:
            console.print("\n[bold]Select a device to configure:[/bold]")
            selection = Prompt.ask(
                "Enter device number, or enter IP address manually",
                default=(
                    ""
                    if not cfg["kasa"].get("device_ip")
                    else cfg["kasa"].get("device_ip")
                ),
            )

            try:
                device_index = int(selection)
                selected_device = next(
                    (d for d in discovered_devices if d["index"] == device_index),
                    None,
                )

                if selected_device:
                    device_ip = selected_device["ip"]
                    device_alias = selected_device["name"]
                    console.print(
                        f"[green]Selected:[/green] {device_alias} at {device_ip}"
                    )
                else:
                    console.print(
                        f"[yellow]No device with index {device_index} found.[/yellow]"
                    )
                    device_ip = Prompt.ask(
                        "Kasa device IP address",
                        default=cfg["kasa"].get("device_ip", ""),
                    )
            except ValueError:
                device_ip = selection
        else:
            device_ip = Prompt.ask(
                "Kasa device IP address",
                default=cfg["kasa"].get("device_ip", ""),
            )

        if device_ip and not device_alias:
            device_alias = Prompt.ask(
                "Kasa device alias",
                default=cfg["kasa"].get("alias", "PC"),
            )

        cfg["kasa"]["device_ip"] = device_ip
        cfg["kasa"]["alias"] = device_alias

        require_auth = Confirm.ask(
            "Does this device require authentication?", default=False
        )

        if require_auth:
            username = Prompt.ask("Username", default=cfg["kasa"].get("username", ""))
            cfg["kasa"]["username"] = username

            password = Prompt.ask(
                "Password",
                default=cfg["kasa"].get("password", ""),
                password=True,
            )
            cfg["kasa"]["password"] = password
        else:
            cfg["kasa"].pop("username", None)
            cfg["kasa"].pop("password", None)

        if device_ip:
            console.print("Testing connection to Kasa device...")
            try:
                device = kasa.KasaDevice(
                    device_ip,
                    device_alias,
                    username=cfg["kasa"].get("username"),
                    password=cfg["kasa"].get("password"),
                )

                success, error = device.validate_connection()

                if success:
                    display_mgr.show_success("Kasa Device", "Connection successful!")
                else:
                    display_mgr.show_error("Kasa Device", f"Connection failed: {error}")
            except Exception as e:
                display_mgr.show_error("Kasa Device", f"Connection test failed: {e}")
        else:
            console.print(
                "[yellow]Note: Device IP is required to test connection.[/yellow]"
            )

        config.save_config(cfg)
        display_mgr.show_success("Configuration", "Kasa settings saved successfully!")

        console.print("\n[bold]Next steps:[/bold]")
        console.print(
            "- Run [bold cyan]wattwise[/bold cyan] to see current power usage"
        )
        console.print(
            "- Run [bold cyan]wattwise --watch[/bold cyan] "
            "to continuously monitor power usage"
        )

    except Exception as e:
        logger.error(f"Configuration error: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@config_app.command("fix-permissions")
def fix_permissions() -> None:
    """Fix permissions on configuration and data directories."""
    try:
        console.print("[bold blue]WattWise - Fixing Directory Permissions[/bold blue]")

        config_dir = config.get_config_dir()
        data_dir = config.get_data_dir()

        config_dir_exists = os.path.exists(config_dir)
        data_dir_exists = os.path.exists(data_dir)

        config_dir_writable = (
            os.access(config_dir, os.W_OK) if config_dir_exists else False
        )
        data_dir_writable = os.access(data_dir, os.W_OK) if data_dir_exists else False

        need_sudo = (config_dir_exists and not config_dir_writable) or (
            data_dir_exists and not data_dir_writable
        )

        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)

        try:
            os.chmod(config_dir, 0o755)
            console.print(
                f"[green]\\u2713[/green] Set permissions on "
                f"config directory: {config_dir}"
            )
        except Exception as e:
            console.print(
                f"[red]\\u2717[/red] Could not set permissions "
                f"on config directory: {e}"
            )
            need_sudo = True

        try:
            os.chmod(data_dir, 0o755)
            console.print(
                f"[green]\\u2713[/green] Set permissions on "
                f"data directory: {data_dir}"
            )
        except Exception as e:
            console.print(
                f"[red]\\u2717[/red] Could not set permissions "
                f"on data directory: {e}"
            )
            need_sudo = True

        config_path = config.get_config_path()
        if os.path.exists(config_path):
            try:
                os.chmod(config_path, 0o644)
                console.print(
                    f"[green]\\u2713[/green] Set permissions "
                    f"on config file: {config_path}"
                )
            except Exception as e:
                console.print(
                    f"[red]\\u2717[/red] Could not set "
                    f"permissions on config file: {e}"
                )
                need_sudo = True

        token_path = config.get_token_path()
        if os.path.exists(token_path):
            try:
                os.chmod(token_path, 0o600)
                console.print(
                    f"[green]\\u2713[/green] Set permissions "
                    f"on token file: {token_path}"
                )
            except Exception as e:
                console.print(
                    f"[red]\\u2717[/red] Could not set "
                    f"permissions on token file: {e}"
                )
                need_sudo = True
                try:
                    os.remove(token_path)
                    console.print(
                        f"[yellow]![/yellow] Removed problematic "
                        f"token file: {token_path}"
                    )
                except Exception as remove_error:
                    console.print(
                        f"[red]\\u2717[/red] Could not remove "
                        f"problematic token file: {remove_error}"
                    )

        history_path = os.path.join(data_dir, "history.json")
        if os.path.exists(history_path):
            try:
                os.chmod(history_path, 0o644)
                console.print(
                    f"[green]\\u2713[/green] Set permissions "
                    f"on history file: {history_path}"
                )
            except Exception as e:
                console.print(
                    f"[red]\\u2717[/red] Could not set "
                    f"permissions on history file: {e}"
                )
                need_sudo = True

        console.print("\n[bold green]Permission check complete![/bold green]")

        if need_sudo:
            console.print(
                "\n[bold yellow]Permissions could not be fully fixed.[/bold yellow]"
            )
            console.print(
                "Run the following command to take ownership "
                "of the configuration files:"
            )
            console.print(
                "[bold cyan]sudo chown -R $USER:$USER "
                "~/.config/wattwise "
                "~/.local/share/wattwise[/bold cyan]"
            )
        else:
            console.print(
                "\n[bold green]All permissions set correctly!" "[/bold green]"
            )
            console.print(
                "You can now run [bold cyan]wattwise config "
                "kasa[/bold cyan] to set up your device."
            )

        console.print(
            "\n[dim]If you continue to have issues, you can always try:[/dim]"
        )
        console.print(
            "[dim cyan]sudo chown -R $USER:$USER "
            "~/.config/wattwise "
            "~/.local/share/wattwise[/dim cyan]"
        )

    except Exception as e:
        logger.error(f"Fix permissions error: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print(
            "[bold yellow]Try running the following command instead:[/bold yellow]"
        )
        console.print(
            "[bold cyan]sudo chown -R $USER:$USER "
            "~/.config/wattwise "
            "~/.local/share/wattwise[/bold cyan]"
        )
        raise typer.Exit(code=1)


@app.command(hidden=True)
def view(
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Continuously watch power usage"
    ),
    interval: int = typer.Option(
        1,
        "--interval",
        "-i",
        help="Refresh interval in seconds when watching",
        min=1,
        max=60,
    ),
    minutes: int = typer.Option(
        5,
        "--minutes",
        "-m",
        help="Minutes of history to analyze for trends",
        min=1,
        max=60,
    ),
    show_current: bool = typer.Option(
        False,
        "--current",
        "-c",
        help="Show current amperage data when available",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use mock data instead of connecting to Home Assistant",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Force using a specific data source: 'homeassistant' or 'kasa'",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output only the raw watts value as a number, suitable for use in scripts",
    ),
    discover: bool = typer.Option(
        False,
        "--discover",
        "-d",
        help="Discover and show available Kasa devices on your network",
    ),
    device: Optional[str] = typer.Option(
        None,
        "--device",
        help="Select a specific device by name",
    ),
    no_alerts: bool = typer.Option(
        False,
        "--no-alerts",
        help="Suppress power alerts in watch mode",
    ),
) -> None:
    """View current power usage from smart plugs."""
    try:
        if discover:
            from . import kasa

            console.print(
                "[bold blue]WattWise - Discovering Kasa Devices[/bold blue]\n"
            )
            kasa.discover_devices_sync(timeout=10)
            console.print(
                "\nTo configure a device, run: "
                "[bold cyan]wattwise config kasa[/bold cyan]"
            )
            return

        config_dir = config.get_config_dir()
        if not os.access(config_dir, os.W_OK):
            display_mgr = display.DisplayManager({})
            display_mgr.show_error(
                "Permission Error",
                "No write permission on config directory. "
                "Please run the following command to fix:",
            )
            console.print("\n[bold cyan]wattwise config fix-permissions[/bold cyan]")
            console.print("\nIf that doesn't work, you may need to run:")
            console.print(
                "[bold cyan]sudo chown -R $USER:$USER "
                "~/.config/wattwise "
                "~/.local/share/wattwise[/bold cyan]"
            )
            raise typer.Exit(code=1)

        cfg = config.load_config()
        display_mgr = display.DisplayManager(cfg)

        # --- Resolve data source ---
        # If --device is specified, look it up in multi-device config
        if device:
            devices = _get_devices_from_config(cfg)
            dev_cfg = next((d for d in devices if d.get("name") == device), None)
            if not dev_cfg:
                display_mgr.show_error(
                    "Device Error",
                    f"Device '{device}' not found. "
                    "Run [bold cyan]wattwise devices list"
                    "[/bold cyan] to see available devices.",
                )
                raise typer.Exit(code=1)

            data_source, source_name = _create_data_source(
                dev_cfg, show_current=show_current, mock=mock
            )

            if not mock:
                success, error = data_source.validate_connection()
                if not success:
                    display_mgr.show_error(
                        "Connection Error",
                        f"Failed to connect to {source_name}: {error}",
                    )
                    raise typer.Exit(code=1)
        else:
            # Legacy single-device resolution
            ha_config = cfg["homeassistant"]
            kasa_config = cfg["kasa"]

            use_ha = source == "homeassistant" or (
                source is None and ha_config["host"] and ha_config["token"]
            )
            use_kasa = source == "kasa" or (
                source is None and kasa_config.get("device_ip") and not use_ha
            )

            if not use_ha and not use_kasa and not mock:
                from . import kasa

                display_mgr.show_error(
                    "Configuration Error",
                    "No data sources configured. " "Set up a data source first.",
                )

                console.print(
                    "\n[bold]Looking for Kasa devices on your network...[/bold]"
                )

                try:
                    discovered_devices = kasa.discover_devices_sync(timeout=5)

                    if discovered_devices:
                        console.print(
                            "\n[bold]To configure one of these devices, run:[/bold]"
                        )
                        console.print("[bold cyan]wattwise config kasa[/bold cyan]")
                    else:
                        console.print(
                            "\n[yellow]No Kasa devices found on your network.[/yellow]"
                        )
                        console.print(
                            "If you have Kasa devices, make sure "
                            "they are powered on and connected "
                            "to your network."
                        )
                except Exception as e:
                    logger.warning(f"Error discovering devices: {e}")

                console.print(
                    "\n[bold]Please run one of the following "
                    "commands to configure WattWise:[/bold]"
                )
                console.print(
                    "- [bold cyan]wattwise config kasa"
                    "[/bold cyan] - Configure Kasa smart plug"
                )
                console.print(
                    "- [bold cyan]wattwise config ha"
                    "[/bold cyan] - Configure Home Assistant"
                )
                console.print("\nTo discover all available Kasa devices, run:")
                console.print("[bold cyan]wattwise --discover[/bold cyan]")

                raise typer.Exit(code=1)

            # Create data source — both backends now implement the same interface
            if use_ha or mock:
                current_entity_id = (
                    ha_config.get("current_entity_id") if show_current else None
                )
                ha_client = homeassistant.HomeAssistant(
                    ha_config["host"],
                    ha_config["token"],
                    ha_config["entity_id"],
                    current_entity_id=current_entity_id,
                    mock=mock,
                )

                success, error = ha_client.validate_connection()
                if not success and not mock:
                    display_mgr.show_error(
                        "Home Assistant Error",
                        f"Failed to connect to Home Assistant: {error}",
                    )
                    raise typer.Exit(code=1)

                if mock:
                    console.print(
                        "[bold yellow]Using mock data mode - "
                        "no real connection to "
                        "Home Assistant[/bold yellow]"
                    )

                data_source = ha_client
                source_name = "Home Assistant"
            else:
                from . import kasa

                try:
                    kasa_client = kasa.KasaDevice(
                        kasa_config["device_ip"],
                        kasa_config.get("alias", ""),
                        username=kasa_config.get("username"),
                        password=kasa_config.get("password"),
                    )

                    data_source = kasa_client
                    source_name = "Kasa Smart Plug"
                except Exception as e:
                    display_mgr.show_error(
                        "Kasa Connection Error",
                        f"Failed to initialize Kasa device: {e}",
                    )
                    console.print(
                        "\nYou may need to run this command to fix permission issues:"
                    )
                    console.print(
                        "[bold cyan]wattwise config fix-permissions[/bold cyan]"
                    )
                    raise typer.Exit(code=1)

        # --- Set up alerts ---
        alert_mgr = None
        if watch and not no_alerts:
            alert_mgr = AlertManager(cfg)

        # --- Set up cost config ---
        energy_cfg = cfg.get("energy", {})

        # Load history for watch mode
        if watch and os.path.exists(_get_history_file()) and not mock:
            try:
                with open(_get_history_file(), "r") as f:
                    history_data = json.load(f)

                    # Both backends now use consistent attribute names
                    power_key = (
                        "power_history"
                        if hasattr(data_source, "power_history")
                        else "history"
                    )
                    power_list = getattr(data_source, power_key, [])
                    if not power_list:
                        setattr(data_source, power_key, history_data.get("power", []))

                    if show_current and hasattr(data_source, "current_history"):
                        if not data_source.current_history:
                            data_source.current_history = history_data.get(
                                "current", []
                            )

                    loaded_power = len(getattr(data_source, power_key, []))
                    loaded_current = len(getattr(data_source, "current_history", []))
                    logger.info(
                        f"Loaded {loaded_power} power readings and "
                        f"{loaded_current} current readings from history"
                    )
            except Exception as e:
                logger.warning(f"Could not load history from file: {e}")

        try:
            if watch:
                _watch_power_usage(
                    data_source,
                    display_mgr,
                    interval,
                    minutes,
                    show_current,
                    source_name,
                    raw,
                    alert_manager=alert_mgr,
                    energy_config=energy_cfg,
                )
            else:
                _fetch_and_display_usage(
                    data_source,
                    display_mgr,
                    show_current,
                    source_name,
                    raw,
                    energy_config=energy_cfg,
                )
        except KeyboardInterrupt:
            if not raw:
                console.print("\n[bold]Monitoring stopped.[/bold]")

            if watch:
                _save_history(data_source)

    except config.ConfigError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        console.print("\nYou may need to run this command to fix permission issues:")
        console.print("[bold cyan]wattwise config fix-permissions[/bold cyan]")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"View error: {e}")
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


def _save_history(data_source: Any) -> None:
    """Save power/current history to file."""
    try:
        power_history: list[Any] = []
        if hasattr(data_source, "power_history"):
            power_history = data_source.power_history
        elif hasattr(data_source, "history"):
            power_history = data_source.history

        if power_history:
            with open(_get_history_file(), "w") as f:
                json.dump(
                    {
                        "power": power_history,
                        "current": getattr(data_source, "current_history", []),
                    },
                    f,
                )
            logger.info(f"Saved history to {_get_history_file()}")
    except Exception as e:
        logger.warning(f"Could not save history to file: {e}")


def _watch_power_usage(
    data_source: Any,
    display_mgr: display.DisplayManager,
    interval: int,
    minutes: int,
    show_current: bool,
    source_name: str,
    raw: bool,
    alert_manager: AlertManager | None = None,
    energy_config: dict[str, Any] | None = None,
) -> None:
    """Continuously watch and display power usage from smart plugs."""
    is_current_capable = isinstance(data_source, CurrentCapable)

    def get_power() -> float | None:
        try:
            watts: float | None = data_source.get_power_usage()
            # Check alerts
            if watts is not None and alert_manager is not None:
                alert_msg = alert_manager.check(watts)
                if alert_msg and not raw:
                    console.print(f"[bold red]ALERT:[/bold red] {alert_msg}")
            return watts
        except Exception as e:
            logger.error(f"Error getting power data: {e}")
            return None

    def get_power_trend(mins: int) -> dict[str, Any] | None:
        result: dict[str, Any] | None = data_source.get_power_trend(mins)
        return result

    def get_current() -> float | None:
        if show_current and is_current_capable:
            try:
                result: float | None = data_source.get_current_amperage()
                return result
            except Exception as e:
                logger.error(f"Error getting current data: {e}")
                return None
        return None

    def get_current_trend(mins: int) -> dict[str, Any] | None:
        if show_current and is_current_capable:
            trend: dict[str, Any] | None = data_source.get_current_trend(mins)
            return trend
        return None

    display_mgr.display_continuous_usage(
        get_power,
        get_power_trend,
        source_name,
        interval,
        get_current_callback=get_current,
        get_current_trend_callback=get_current_trend,
        show_current=show_current,
        raw=raw,
        energy_config=energy_config,
    )


def _fetch_and_display_usage(
    data_source: Any,
    display_mgr: display.DisplayManager,
    show_current: bool,
    source_name: str,
    raw: bool,
    energy_config: dict[str, Any] | None = None,
) -> None:
    """Fetch and display power usage for a single reading from a smart plug."""
    try:
        watts = data_source.get_power_usage()

        amperes = None
        if show_current and isinstance(data_source, CurrentCapable):
            amperes = data_source.get_current_amperage()

        if watts is not None:
            if raw:
                sys.stdout.write(f"{watts:.0f}\n")
                sys.stdout.flush()
            else:
                display_mgr.display_current_usage(
                    watts, source_name, current_amperes=amperes
                )
                # Show cost estimate if energy config is present
                if energy_config and energy_config.get("rate"):
                    rate = energy_config["rate"]
                    symbol = energy_config.get("currency_symbol", "$")
                    costs = estimate_costs(watts, rate, symbol)
                    console.print(
                        f"[dim]Est. cost: {costs['hourly']}/hr | "
                        f"{costs['daily']}/day | {costs['monthly']}/mo[/dim]"
                    )
        else:
            if raw:
                sys.exit(1)
            else:
                display_mgr.show_error(
                    "Data Error",
                    f"Could not get power usage data from {source_name}",
                )
    except Exception as e:
        if raw:
            sys.exit(1)
        else:
            display_mgr.show_error("Error", str(e))


# ---------------------------------------------------------------------------
# Phase 3B: Export command
# ---------------------------------------------------------------------------


@app.command("export")
def export_cmd(
    fmt: str = typer.Option("csv", "--format", "-f", help="Output format: csv or json"),
    output: str = typer.Option(
        "wattwise_export.csv",
        "--output",
        "-o",
        help="Output file path",
    ),
    start: Optional[str] = typer.Option(
        None,
        "--start",
        help="Filter from ISO date (e.g. 2025-01-01)",
    ),
    end: Optional[str] = typer.Option(
        None,
        "--end",
        help="Filter to ISO date (e.g. 2025-12-31)",
    ),
) -> None:
    """Export power usage history to CSV or JSON."""
    history_file = _get_history_file()
    if not os.path.exists(history_file):
        console.print(
            "[bold red]Error:[/bold red] No history data found. "
            "Run [bold cyan]wattwise --watch[/bold cyan] first to collect data."
        )
        raise typer.Exit(code=1)

    try:
        count = export_history(history_file, output, fmt=fmt, start=start, end=end)
        console.print(f"[bold green]Exported {count} records to {output}[/bold green]")
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Export error:[/bold red] {e}")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Phase 3C: Cost command
# ---------------------------------------------------------------------------


@app.command("cost")
def cost_cmd(
    watts: float = typer.Option(..., "--watts", "-W", help="Power draw in watts"),
    rate: Optional[float] = typer.Option(
        None, "--rate", "-r", help="Energy rate per kWh (overrides config)"
    ),
    symbol: Optional[str] = typer.Option(
        None, "--symbol", help="Currency symbol (overrides config)"
    ),
) -> None:
    """Calculate energy costs for a given power draw."""
    cfg = config.load_config()
    energy_cfg = cfg.get("energy", {})
    effective_rate = rate if rate is not None else energy_cfg.get("rate", 0.12)
    effective_symbol = (
        symbol if symbol is not None else energy_cfg.get("currency_symbol", "$")
    )

    costs = estimate_costs(watts, effective_rate, effective_symbol)
    console.print(f"\n[bold]Energy cost estimate for {watts:.0f}W:[/bold]")
    console.print(f"  Hourly:  {costs['hourly']}")
    console.print(f"  Daily:   {costs['daily']}")
    console.print(f"  Monthly: {costs['monthly']}")
    console.print(f"  Yearly:  {costs['yearly']}")
    console.print(f"\n[dim]Rate: {effective_symbol}{effective_rate:.4f}/kWh[/dim]")


# ---------------------------------------------------------------------------
# Phase 3A: Devices commands
# ---------------------------------------------------------------------------


def _get_devices_from_config(
    cfg: dict[str, Any], allow_legacy: bool = True
) -> list[dict[str, Any]]:
    """Get the devices list, synthesizing from legacy config if needed."""
    if "devices" in cfg:
        devices: list[dict[str, Any]] = cfg.get("devices") or []
        return devices
    if not allow_legacy:
        return []

    # Synthesize from legacy single-device config
    devices = []
    ha = cfg.get("homeassistant", {})
    if ha.get("host") and ha.get("token"):
        devices.append(
            {
                "name": ha.get("device_name", "HomeAssistant"),
                "type": "homeassistant",
                "host": ha["host"],
                "token": ha["token"],
                "entity_id": ha.get("entity_id", ""),
                "current_entity_id": ha.get("current_entity_id", ""),
            }
        )

    kasa_cfg = cfg.get("kasa", {})
    if kasa_cfg.get("device_ip"):
        devices.append(
            {
                "name": kasa_cfg.get("alias", "Kasa Device"),
                "type": "kasa",
                "device_ip": kasa_cfg["device_ip"],
                "alias": kasa_cfg.get("alias", ""),
                "username": kasa_cfg.get("username"),
                "password": kasa_cfg.get("password"),
            }
        )

    return devices


def _create_data_source(
    device_cfg: dict[str, Any], show_current: bool = False, mock: bool = False
) -> tuple[Any, str]:
    """Create a data source from a device config dict.

    Returns (data_source, source_name).
    """
    dev_type = device_cfg.get("type", "kasa")

    if dev_type == "homeassistant":
        current_entity_id = (
            device_cfg.get("current_entity_id") if show_current else None
        )
        ha_client = homeassistant.HomeAssistant(
            device_cfg.get("host", ""),
            device_cfg.get("token", ""),
            device_cfg.get("entity_id", ""),
            current_entity_id=current_entity_id,
            mock=mock,
        )
        return ha_client, device_cfg.get("name", "Home Assistant")

    # Default to kasa
    from . import kasa as kasa_mod

    kasa_client = kasa_mod.KasaDevice(
        device_cfg.get("device_ip", ""),
        device_cfg.get("alias", ""),
        username=device_cfg.get("username"),
        password=device_cfg.get("password"),
    )
    return kasa_client, device_cfg.get("name", "Kasa Smart Plug")


@devices_app.command("list")
def devices_list() -> None:
    """List all configured devices."""
    cfg = config.load_config()
    devices = _get_devices_from_config(cfg)

    if not devices:
        console.print("[yellow]No devices configured.[/yellow]")
        console.print(
            "Run [bold cyan]wattwise devices add[/bold cyan] "
            "or [bold cyan]wattwise config kasa[/bold cyan] to add one."
        )
        return

    from rich.table import Table  # type: ignore[import-not-found]

    table = Table(title="Configured Devices")
    table.add_column("#", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Type")
    table.add_column("Address")

    for i, dev in enumerate(devices, 1):
        dev_type = dev.get("type", "kasa")
        addr = (
            dev.get("host", "")
            if dev_type == "homeassistant"
            else dev.get("device_ip", "")
        )
        table.add_row(str(i), dev.get("name", ""), dev_type, addr)

    console.print(table)


@devices_app.command("add")
def devices_add(
    name: str = typer.Option(..., "--name", "-n", help="Device name"),
    dev_type: str = typer.Option(
        ..., "--type", "-t", help="Device type: 'kasa' or 'homeassistant'"
    ),
    device_ip: Optional[str] = typer.Option(
        None, "--ip", help="Kasa device IP address"
    ),
    host: Optional[str] = typer.Option(None, "--host", help="Home Assistant host URL"),
    token: Optional[str] = typer.Option(None, "--token", help="Home Assistant token"),
    entity_id: Optional[str] = typer.Option(
        None, "--entity-id", help="Home Assistant power entity ID"
    ),
    current_entity_id: Optional[str] = typer.Option(
        None, "--current-entity-id", help="Home Assistant current entity ID"
    ),
) -> None:
    """Add a new device to monitor."""
    if dev_type not in ("kasa", "homeassistant"):
        console.print(
            "[bold red]Error:[/bold red] --type must be 'kasa' or 'homeassistant'"
        )
        raise typer.Exit(code=1)

    cfg = config.load_config()
    devices = _get_devices_from_config(cfg)
    if "devices" not in cfg:
        cfg["devices"] = devices

    # Check for duplicate name
    if any(d.get("name") == name for d in devices):
        console.print(f"[bold red]Error:[/bold red] Device '{name}' already exists.")
        raise typer.Exit(code=1)

    new_device: dict[str, Any] = {"name": name, "type": dev_type}
    if dev_type == "kasa":
        if not device_ip:
            console.print(
                "[bold red]Error:[/bold red] --ip is required for kasa devices."
            )
            raise typer.Exit(code=1)
        new_device["device_ip"] = device_ip
        new_device["alias"] = name
    else:
        if not host or not token or not entity_id:
            console.print(
                "[bold red]Error:[/bold red] "
                "--host, --token, and --entity-id are "
                "required for homeassistant devices."
            )
            raise typer.Exit(code=1)
        new_device["host"] = host
        new_device["token"] = token
        new_device["entity_id"] = entity_id
        if current_entity_id:
            new_device["current_entity_id"] = current_entity_id

    devices.append(new_device)
    cfg["devices"] = devices
    config.save_config(cfg)
    console.print(f"[bold green]Added device '{name}' ({dev_type})[/bold green]")


@devices_app.command("remove")
def devices_remove(
    name: str = typer.Option(..., "--name", "-n", help="Device name to remove"),
) -> None:
    """Remove a configured device."""
    cfg = config.load_config()
    devices = _get_devices_from_config(cfg)
    if "devices" not in cfg:
        cfg["devices"] = devices

    original_len = len(devices)
    devices = [d for d in devices if d.get("name") != name]

    if len(devices) == original_len:
        console.print(f"[bold red]Error:[/bold red] Device '{name}' not found.")
        raise typer.Exit(code=1)

    cfg["devices"] = devices
    config.save_config(cfg)
    console.print(f"[bold green]Removed device '{name}'[/bold green]")


# ---------------------------------------------------------------------------
# Callback (main entry point)
# ---------------------------------------------------------------------------


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    watch: bool = typer.Option(
        False, "--watch", "-w", help="Continuously watch power usage"
    ),
    interval: int = typer.Option(
        1,
        "--interval",
        "-i",
        help="Refresh interval in seconds when watching",
        min=1,
        max=60,
    ),
    minutes: int = typer.Option(
        5,
        "--minutes",
        "-m",
        help="Minutes of history to analyze for trends",
        min=1,
        max=60,
    ),
    show_current: bool = typer.Option(
        False,
        "--current",
        "-c",
        help="Show current amperage data when available",
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        help="Use mock data instead of connecting to Home Assistant",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Force using a specific data source: 'homeassistant' or 'kasa'",
    ),
    raw: bool = typer.Option(
        False,
        "--raw",
        help="Output only the raw watts value as a number, suitable for use in scripts",
    ),
    discover: bool = typer.Option(
        False,
        "--discover",
        "-d",
        help="Discover and show available Kasa devices on your network",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose (debug) logging output",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress all logging except errors",
    ),
    device: Optional[str] = typer.Option(
        None,
        "--device",
        help="Select a specific device by name (from multi-device config)",
    ),
    no_alerts: bool = typer.Option(
        False,
        "--no-alerts",
        help="Suppress power alerts in watch mode",
    ),
) -> None:
    """
    WattWise - Monitor power usage from smart plugs with Home Assistant or Kasa.

    Examples:
      wattwise                   Show current power usage (single reading)
      wattwise --watch           Monitor power continuously with charts
      wattwise --current         Show power and current (single reading)
      wattwise --current --watch Monitor power and current continuously
      wattwise --raw             Output only the raw watts value for scripting use
      wattwise --mock            Use mock data for testing (no real connection)
      wattwise --discover        Find all Kasa devices on your network
      wattwise --device "PC"     Monitor a specific named device
      wattwise cost --watts 500  Estimate energy costs for 500W
      wattwise export            Export history to CSV
      wattwise devices list      List configured devices
      wattwise -v                Enable verbose logging
      wattwise -q                Suppress non-error logging
      wattwise config kasa       Configure Kasa smart plug
      wattwise config ha         Configure Home Assistant
    """
    _setup_logging(verbose=verbose, quiet=quiet)

    if ctx.invoked_subcommand is None:
        ctx.invoke(
            view,
            watch=watch,
            interval=interval,
            minutes=minutes,
            show_current=show_current,
            mock=mock,
            source=source,
            raw=raw,
            discover=discover,
            device=device,
            no_alerts=no_alerts,
        )


def main() -> None:
    """Main entry point for the application."""
    try:
        app()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        console.print(f"[bold red]Unhandled error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
