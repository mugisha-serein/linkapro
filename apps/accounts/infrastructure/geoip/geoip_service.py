from __future__ import annotations

import logging
from typing import Any

from django.contrib.gis.geoip2 import GeoIP2
from geoip2.errors import AddressNotFoundError

logger = logging.getLogger(__name__)


class GeoIPService:
    """
    Infrastructure service for GeoIP lookups.
    Wraps Django's GeoIP2 utility which uses MaxMind's GeoLite2 databases.
    """

    def __init__(self) -> None:
        try:
            # GeoIP2 will look for GEOIP_PATH in Django settings
            self._geoip = GeoIP2()
            self._available = True
        except Exception as e:
            logger.warning("GeoIP2 initialization failed: %s. GeoIP features will be disabled.", e)
            self._geoip = None
            self._available = False

    def get_location_data(self, ip_address: str) -> dict[str, Any] | None:
        """
        Retrieves city and country information for a given IP address.
        Returns None if the IP is local, not found, or service is unavailable.
        """
        if not self._available or not ip_address:
            return None

        # Skip lookups for local addresses
        if ip_address in ("127.0.0.1", "::1") or ip_address.startswith("192.168."):
            return None

        try:
            return self._geoip.city(ip_address)
        except AddressNotFoundError:
            return None
        except Exception as e:
            logger.error("Unexpected error during GeoIP lookup for %s: %s", ip_address, e)
            return None

    def get_country_code(self, ip_address: str) -> str | None:
        """
        Convenience method to retrieve only the ISO country code.
        """
        data = self.get_location_data(ip_address)
        return data.get("country_code") if data else None