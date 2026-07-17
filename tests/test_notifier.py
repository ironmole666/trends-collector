import unittest
from unittest.mock import Mock

from trends_collector.notifier import Notifier


def _config(*, smtp=None, http=None):
    return {
        "notifications": {
            "email": smtp or {"enabled": False},
            "http_email": http or {"enabled": False},
        }
    }


class NotifierFallbackTests(unittest.TestCase):
    def test_incomplete_smtp_does_not_block_ready_http_channel(self):
        notifier = Notifier(_config(
            smtp={"enabled": True},
            http={
                "enabled": True,
                "provider": "resend",
                "api_key": "test-key",
                "from_addr": "sender@example.com",
                "to_addrs": ["recipient@example.com"],
            },
        ))
        notifier._email.send = Mock(return_value=True)
        notifier._http_email.send = Mock(return_value=True)

        result = notifier._send_email_with_fallback("report", "subject")

        self.assertTrue(result)
        notifier._email.send.assert_not_called()
        notifier._http_email.send.assert_called_once_with("report", "subject")

    def test_http_channel_is_used_when_smtp_send_fails(self):
        notifier = Notifier(_config(
            smtp={
                "enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_user": "user",
                "smtp_password": "password",
                "from_addr": "sender@example.com",
                "to_addrs": ["recipient@example.com"],
            },
            http={
                "enabled": True,
                "provider": "resend",
                "api_key": "test-key",
                "from_addr": "sender@example.com",
                "to_addrs": ["recipient@example.com"],
            },
        ))
        notifier._email.send = Mock(return_value=False)
        notifier._http_email.send = Mock(return_value=True)

        result = notifier._send_email_with_fallback("report", "subject")

        self.assertTrue(result)
        notifier._email.send.assert_called_once_with("report", "subject")
        notifier._http_email.send.assert_called_once_with("report", "subject")

    def test_successful_smtp_does_not_send_duplicate_http_email(self):
        notifier = Notifier(_config(
            smtp={
                "enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_user": "user",
                "smtp_password": "password",
                "from_addr": "sender@example.com",
                "to_addrs": ["recipient@example.com"],
            },
            http={
                "enabled": True,
                "provider": "resend",
                "api_key": "test-key",
                "from_addr": "sender@example.com",
                "to_addrs": ["recipient@example.com"],
            },
        ))
        notifier._email.send = Mock(return_value=True)
        notifier._http_email.send = Mock(return_value=True)

        result = notifier._send_email_with_fallback("report", "subject")

        self.assertTrue(result)
        notifier._email.send.assert_called_once_with("report", "subject")
        notifier._http_email.send.assert_not_called()

    def test_no_usable_channel_reports_failure(self):
        notifier = Notifier(_config(
            smtp={"enabled": True},
            http={"enabled": True, "provider": "resend"},
        ))

        self.assertFalse(notifier._send_email_with_fallback("report", "subject"))


if __name__ == "__main__":
    unittest.main()
