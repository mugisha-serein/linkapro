import uuid

from django.db import models


class Inquiry(models.Model):
    class ProviderChoices(models.TextChoices):
        RECAPTCHA = 'recaptcha', 'reCAPTCHA v3'
        HCAPTCHA = 'hcaptcha', 'hCaptcha'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    captcha_provider = models.CharField(
        max_length=20,
        choices=ProviderChoices.choices,
        default=ProviderChoices.RECAPTCHA,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Inquiry from {self.name} <{self.email}>'
