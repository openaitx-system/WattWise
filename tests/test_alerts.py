"""Tests for wattwise.alerts module."""

from wattwise.alerts import AlertManager


class TestAlertManagerDisabled:
    def test_disabled_by_default(self):
        mgr = AlertManager({})
        assert mgr.check(9999) is None

    def test_disabled_explicit(self):
        mgr = AlertManager({"alerts": {"enabled": False, "threshold": 100}})
        assert mgr.check(9999) is None


class TestAlertManagerEnabled:
    def test_below_threshold_no_alert(self):
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 1000,
                    "sustained_seconds": 0,
                }
            }
        )
        assert mgr.check(500) is None

    def test_above_threshold_immediate(self):
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 1000,
                    "sustained_seconds": 0,
                }
            }
        )
        msg = mgr.check(1500)
        assert msg is not None
        assert "1500" in msg
        assert "1000" in msg

    def test_sustained_duration_not_met(self):
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 1000,
                    "sustained_seconds": 60,
                }
            }
        )
        # First check starts the timer
        assert mgr.check(1500) is None
        # Immediately checking again — not enough time elapsed
        assert mgr.check(1500) is None

    def test_alert_resets_on_drop(self):
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 1000,
                    "sustained_seconds": 0,
                }
            }
        )
        # Trigger alert
        msg = mgr.check(1500)
        assert msg is not None

        # Drop below threshold
        mgr.check(500)

        # Should be reset — next spike triggers fresh
        assert mgr._alert_sent is False
        assert mgr._above_threshold_since is None

    def test_alert_not_repeated(self):
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 1000,
                    "sustained_seconds": 0,
                }
            }
        )
        # First alert fires
        msg1 = mgr.check(1500)
        assert msg1 is not None

        # Subsequent checks should not re-fire
        msg2 = mgr.check(1500)
        assert msg2 is None


class TestAlertNotifications:
    def test_webhook_notification(self, mocker):
        mock_post = mocker.patch("wattwise.alerts.requests.post")
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 100,
                    "sustained_seconds": 0,
                    "notifications": [
                        {"type": "webhook", "url": "https://example.com/hook"},
                    ],
                }
            }
        )
        mgr.check(200)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://example.com/hook"

    def test_command_notification(self, mocker):
        mock_run = mocker.patch("wattwise.alerts.subprocess.run")
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 100,
                    "sustained_seconds": 0,
                    "notifications": [
                        {"type": "command", "command": "echo alert"},
                    ],
                }
            }
        )
        mgr.check(200)
        mock_run.assert_called_once()

    def test_failed_notification_does_not_raise(self, mocker):
        mocker.patch(
            "wattwise.alerts.requests.post",
            side_effect=Exception("network error"),
        )
        mgr = AlertManager(
            {
                "alerts": {
                    "enabled": True,
                    "threshold": 100,
                    "sustained_seconds": 0,
                    "notifications": [
                        {"type": "webhook", "url": "https://example.com/hook"},
                    ],
                }
            }
        )
        # Should not raise
        msg = mgr.check(200)
        assert msg is not None
