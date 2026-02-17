"""Power usage alerting for WattWise."""

import logging
import os
import subprocess
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class AlertManager:
    """Monitors power readings and fires alerts when thresholds are exceeded."""

    def __init__(self, config: dict[str, Any]) -> None:
        alert_cfg = config.get("alerts", {})
        self.enabled: bool = alert_cfg.get("enabled", False)
        self.threshold: float = alert_cfg.get("threshold", 1000)
        self.sustained_seconds: int = alert_cfg.get("sustained_seconds", 60)
        self.notifications: list[dict[str, Any]] = alert_cfg.get("notifications", [])
        self._above_threshold_since: float | None = None
        self._alert_sent: bool = False

    def check(self, watts: float) -> str | None:
        """Check whether an alert should fire.

        Returns an alert message string if the threshold has been exceeded
        for the sustained duration, otherwise None.
        """
        if not self.enabled:
            return None

        now = time.time()

        if watts >= self.threshold:
            if self._above_threshold_since is None:
                self._above_threshold_since = now

            elapsed = now - self._above_threshold_since
            if elapsed >= self.sustained_seconds and not self._alert_sent:
                self._alert_sent = True
                msg = (
                    f"Power usage {watts:.0f}W exceeds "
                    f"{self.threshold:.0f}W for {elapsed:.0f}s"
                )
                self._send_notifications(msg)
                return msg
        else:
            # Reset when power drops below threshold
            self._above_threshold_since = None
            self._alert_sent = False

        return None

    def _send_notifications(self, message: str) -> None:
        """Send alert notifications via configured channels."""
        for notif in self.notifications:
            notif_type = notif.get("type")
            try:
                if notif_type == "webhook":
                    self._send_webhook(notif, message)
                elif notif_type == "command":
                    self._run_command(notif, message)
                else:
                    logger.warning(f"Unknown notification type: {notif_type}")
            except Exception as e:
                logger.warning(f"Failed to send {notif_type} notification: {e}")

    def _send_webhook(self, notif: dict[str, Any], message: str) -> None:
        """Send a webhook notification."""
        url = notif.get("url", "")
        if not url:
            logger.warning("Webhook notification missing 'url'")
            return
        requests.post(url, json={"text": message}, timeout=10)

    def _run_command(self, notif: dict[str, Any], message: str) -> None:
        """Run a shell command notification."""
        cmd = notif.get("command", "")
        if not cmd:
            logger.warning("Command notification missing 'command'")
            return
        env = dict(os.environ)
        env["WATTWISE_ALERT"] = message
        subprocess.run(cmd, shell=True, timeout=30, env=env, check=False)
