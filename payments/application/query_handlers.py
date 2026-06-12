from payments.application.ports import IPaymentRepository
from payments.application.dtos import PaymentStatusDTO
from payments.application.exceptions import PaymentNotFoundError


class PaymentQueryHandlers:
    def __init__(self, payment_repo: IPaymentRepository):
        self.payment_repo = payment_repo

    def get_payment_status(
        self,
        reference: str,
        user_id=None,
        *,
        allow_global_lookup: bool = False,
    ) -> PaymentStatusDTO:
        payment = self.payment_repo.find_by_reference(reference)
        if not payment or (
            user_id is not None
            and not allow_global_lookup
            and payment.user_id != user_id
        ):
            raise PaymentNotFoundError(f"Payment {reference} not found")

        return PaymentStatusDTO(
            reference=payment.reference,
            status=payment.status.value,
            amount=str(payment.amount.to_decimal()),
            minor_units=payment.amount.minor_units,
            currency=payment.amount.currency.code,
            method=payment.method.value,
            created_at=payment.created_at,
            expires_at=payment.expires_at,
            provider_reference=payment.provider_reference,
        )
