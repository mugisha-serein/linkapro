import logging

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse

logger = logging.getLogger('accounts.oauth')


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom adapter to secure OAuth account linking."""

    def pre_social_login(self, request, sociallogin):
        """Run before social login/sign up completes."""
        email = (
            sociallogin.user.email or
            sociallogin.account.extra_data.get('email')
        )

        if not email:
            return super().pre_social_login(request, sociallogin)

        User = get_user_model()
        existing_user = User.objects.filter(email__iexact=email).first()

        # If this social account is already linked, allow normal flow.
        if sociallogin.is_existing:
            return super().pre_social_login(request, sociallogin)

        # If no local account exists, proceed with social signup.
        if existing_user is None:
            return super().pre_social_login(request, sociallogin)

        # Require provider email verification before linking.
        email_verified = False
        if getattr(sociallogin, 'email_addresses', None):
            email_verified = any(
                getattr(addr, 'verified', False)
                for addr in sociallogin.email_addresses
            )

        if sociallogin.account.extra_data.get('email_verified') is True:
            email_verified = True

        if not email_verified:
            logger.warning(
                'Blocked OAuth login for unverified provider email',
                extra={'email': email, 'provider': sociallogin.account.provider}
            )
            raise ImmediateHttpResponse(
                JsonResponse(
                    {
                        'error': 'OAuth email must be verified before linking with an existing account.'
                    },
                    status=403
                )
            )

        # Require the local account to also be verified.
        if not getattr(existing_user, 'is_verified', False):
            logger.warning(
                'Blocked OAuth login for unverified local account email',
                extra={'email': email, 'user_id': str(existing_user.pk)}
            )
            raise ImmediateHttpResponse(
                JsonResponse(
                    {
                        'error': 'Existing local account must verify its email before linking a social login.'
                    },
                    status=403
                )
            )

        # Allow explicit linking only when the current session belongs to the same user.
        if request.user.is_authenticated and request.user == existing_user:
            logger.info(
                'OAuth account explicitly linked',
                extra={
                    'user_id': str(existing_user.pk),
                    'email': email,
                    'provider': sociallogin.account.provider,
                }
            )
            return super().pre_social_login(request, sociallogin)

        logger.warning(
            'Blocked OAuth auto-linking for existing account without explicit user session',
            extra={'email': email, 'provider': sociallogin.account.provider}
        )
        raise ImmediateHttpResponse(
            JsonResponse(
                {
                    'error': 'An account with this email already exists. Log in first and explicitly link the social account from your profile settings.'
                },
                status=403
            )
        )
