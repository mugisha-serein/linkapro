import geoip2.database
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger('accounts.anomaly')


class GeoIPLocator:
    """
    Resolve IP addresses to geographic locations using MaxMind GeoIP2.
    Falls back gracefully if GeoIP db is not available.
    """

    GEOIP_PATH = settings.BASE_DIR / 'geoip' / 'GeoLite2-City.mmdb'

    def __init__(self):
        self.reader = None
        self._initialize_reader()

    def _initialize_reader(self):
        """Initialize GeoIP database reader."""
        try:
            if self.GEOIP_PATH.exists():
                self.reader = geoip2.database.Reader(str(self.GEOIP_PATH))
                logger.info('GeoIP2 database loaded successfully')
            else:
                logger.warning(f'GeoIP2 database not found at {self.GEOIP_PATH}')
        except Exception as exc:
            logger.error(f'Failed to initialize GeoIP2 reader: {exc}')

    def get_country_code(self, ip_address):
        """
        Get ISO country code for an IP address.
        
        Returns: str (e.g., 'US', 'RW') or None if lookup fails or unavailable.
        """
        if not self.reader or not ip_address or ip_address == 'unknown':
            return None

        try:
            response = self.reader.city(ip_address)
            return response.country.iso_code
        except Exception as exc:
            logger.debug(f'GeoIP lookup failed for {ip_address}: {exc}')
            return None

    def close(self):
        """Close the database reader."""
        if self.reader:
            self.reader.close()


class AnomalyDetector:
    """
    Detect anomalous login patterns (e.g., login from new country).
    Tracks login history and triggers notifications as needed.
    """

    LOCATION_CHANGE_ALERT = True  # Notify on new country login

    def __init__(self):
        self.geoip = GeoIPLocator()

    def detect_anomalies(self, user, ip_address, device_fingerprint=None):
        """
        Check current login against user's history for anomalies.
        
        Returns: dict with anomaly findings and recommended actions
        """
        from ..models import User
        from .login_activity import LoginActivityLog

        anomalies = []
        current_country = self.geoip.get_country_code(ip_address)

        # Check for new country login
        if current_country and self.LOCATION_CHANGE_ALERT:
            recent_countries = (
                LoginActivityLog.objects.filter(user=user)
                .filter(timestamp__gte=timezone.now() - timedelta(days=30))
                .values_list('country_code', flat=True)
                .distinct()
            )

            if current_country not in recent_countries and recent_countries.exists():
                anomalies.append({
                    'type': 'new_location',
                    'country_code': current_country,
                    'action': 'notify_user'
                })
                logger.info(
                    'New country login detected',
                    extra={'user_id': str(user.id), 'country': current_country}
                )

        # Log the login activity
        LoginActivityLog.objects.create(
            user=user,
            ip_address=ip_address,
            country_code=current_country,
            device_fingerprint=device_fingerprint,
            timestamp=timezone.now()
        )

        return {
            'user_id': str(user.id),
            'ip_address': ip_address,
            'country_code': current_country,
            'anomalies': anomalies
        }


# Global instance
anomaly_detector = AnomalyDetector()
