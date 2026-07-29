import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from application.identity.errors import UserNotFoundError
from domain.identity.verification import VerificationResendTooSoon
from interface.common.api_responses import api_error, api_success
from interface.identity.services import (
    get_request_email_verification_use_case,
    get_resend_email_verification_use_case,
)
from interface.identity.throttles import (
    EmailVerificationEmailThrottle,
    EmailVerificationIPThrottle,
    EmailVerificationRateLimited,
)


class EmailVerificationThrottleMixin:
    permission_classes = [IsAuthenticated]
    throttle_classes = [EmailVerificationIPThrottle, EmailVerificationEmailThrottle]

    def throttled(self, request, wait):
        raise EmailVerificationRateLimited(wait=wait, request=request)


class RequestEmailVerificationView(EmailVerificationThrottleMixin, APIView):
    def post(self, request):
        try:
            get_request_email_verification_use_case().execute(user_id=request.user.id)
        except UserNotFoundError:
            return api_error(
                code="email_verification_request_failed",
                message="Unable to request email verification.",
                status=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        return api_success(
            code="email_verification_requested",
            message="Email verification sent.",
            data={},
            status=status.HTTP_202_ACCEPTED,
            request=request,
        )


class ResendEmailVerificationView(EmailVerificationThrottleMixin, APIView):
    def post(self, request, challenge_id):
        try:
            get_resend_email_verification_use_case().execute(
                challenge_id=uuid.UUID(str(challenge_id)),
                user_id=request.user.id,
            )
        except VerificationResendTooSoon:
            return api_error(
                code="email_verification_resend_too_soon",
                message="Please wait before requesting another verification email.",
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                request=request,
            )
        except (UserNotFoundError, ValueError):
            return api_error(
                code="email_verification_not_found",
                message="Verification challenge not found.",
                status=status.HTTP_404_NOT_FOUND,
                request=request,
            )
        return api_success(
            code="email_verification_resent",
            message="Email verification resent.",
            data={},
            status=status.HTTP_202_ACCEPTED,
            request=request,
        )
