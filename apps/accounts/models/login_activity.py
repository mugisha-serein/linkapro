from django.db import models
import uuid


class LoginActivityLog(models.Model):
    """
    Tracks login attempts for anomaly detection and security auditing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='login_activities')
    
    ip_address = models.GenericIPAddressField()
    country_code = models.CharField(max_length=2, null=True, blank=True)  # ISO country code
    device_fingerprint = models.CharField(max_length=64, null=True, blank=True)  # Hash of User-Agent, etc.
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
            models.Index(fields=['country_code', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.user.email} from {self.ip_address} ({self.country_code}) at {self.timestamp}'
