import requests
import uuid
from typing import Tuple, Optional
from django.conf import settings

from payments.application.ports import IProviderGateway, VerifiedTransactionDTO
from payments.domain.value_objects import Money, Currency


class FlutterwaveGateway(IProviderGateway):
    BASE_URL = "https://api.flutterwave.com/v3"

    def __init__(self):
        self.secret_key = settings.FLW_SECRET_KEY
        self.environment = settings.PAYMENT_ENV  # "test" or "live"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def create_payment_link(
        self,
        amount: Money,
        currency: Currency,
        reference: str,
        redirect_url: str,
        customer_email: str,
        customer_name: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Tuple[str, str]:
        url = f"{self.BASE_URL}/payments"
        tx_ref = f"flw_{uuid.uuid4().hex}"
        payload = {
            "tx_ref": tx_ref,
            "amount": str(amount.to_decimal()),
            "currency": currency.code,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
                "name": customer_name or customer_email,
            },
            "customizations": {
                "title": "Linkapro Payment",
                "logo": "https://linkapro.com/logo.png",
            },
            "meta": metadata or {},
        }
        response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
        response.raise_for_status()
        data = response.json()
        if data["status"] != "success":
            raise Exception(data.get("message", "Flutterwave error"))
        return data["data"]["link"], tx_ref

    def verify_transaction(self, provider_reference: str) -> Optional[VerifiedTransactionDTO]:
        url = f"{self.BASE_URL}/transactions/verify_by_reference"
        params = {"tx_ref": provider_reference}
        response = requests.get(url, params=params, headers=self._headers(), timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["status"] != "success":
            return None
        tx = data["data"]
        return VerifiedTransactionDTO(
            provider_reference=provider_reference,
            status="successful" if tx["status"] == "successful" else tx["status"],
            amount_minor_units=int(float(tx["amount"]) * (10 ** self._get_decimals(tx["currency"]))),
            currency_code=tx["currency"],
            raw_response=tx,
        )

    def _get_decimals(self, currency: str) -> int:
        decimals_map = {"RWF": 0, "USD": 2, "EUR": 2, "KES": 2, "GHS": 2, "NGN": 2}
        return decimals_map.get(currency, 2)