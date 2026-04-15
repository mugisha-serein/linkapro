# Domain Service - Security Policy

class SecurityPolicy:
    """
    Domain service for security and anomaly detection policy rules.
    Encapsulates business logic for risk scoring, anomaly detection, and account protection.
    """

    @staticmethod
    def evaluate_risk(login_attempt, context) -> int:
        """Evaluate risk score for a login attempt."""
        # Example: Combine risk factors
        base = 10
        if context.get('ip_reputation') == 'bad':
            base += 40
        if context.get('device_new', False):
            base += 20
        if context.get('geo_anomaly', False):
            base += 15
        return min(base, 100)

    @staticmethod
    def detect_anomaly(login_attempt, context) -> bool:
        """Detect if a login attempt is anomalous."""
        # Example: Unusual location or device
        return context.get('geo_anomaly', False) or context.get('device_new', False)

    @staticmethod
    def should_lock_account(user, context) -> bool:
        """Determine if the user account should be locked."""
        # Example: Too many failed logins
        return user.failed_login_count >= context.get('max_failed_logins', 5)
