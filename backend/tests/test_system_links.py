import unittest
from unittest.mock import patch

from app.integrations.system_links import MagnetOpenError, open_magnet_in_system


class SystemLinkTests(unittest.TestCase):
    @patch("app.integrations.system_links.os.startfile", create=True)
    def test_valid_magnet_uses_windows_protocol_handler(self, startfile) -> None:
        magnet = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
        with patch("app.integrations.system_links.os.name", "nt"):
            open_magnet_in_system(magnet)
        startfile.assert_called_once_with(magnet)

    def test_rejects_non_magnet_protocol(self) -> None:
        with self.assertRaises(MagnetOpenError):
            open_magnet_in_system("https://example.com")


if __name__ == "__main__":
    unittest.main()
