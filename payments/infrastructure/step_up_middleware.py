import json
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from payments.domain.step_up_policy import StepUpPolicy
from payments.domain.value_objects import Money, Currency
from domain.shared.utils import utc_now


class StepUpEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.endswith("/initiate/") and request.method == "POST":
            auth = request.auth
            if auth and hasattr(auth, "payload"):
                step_up = auth.payload.get("step_up", False)
                try:
                    body = json.loads(request.body) if request.body else {}
                except json.JSONDecodeError:
                    body = {}
                amount_str = body.get("amount")
                currency_code = body.get("currency")

                if amount_str and currency_code:
                    try:
                        amount = Decimal(amount_str)
                        money = Money.from_decimal(amount, Currency(currency_code))
                        result = StepUpPolicy.is_step_up_required(money, step_up, utc_now())
                        if result.required:
                            return JsonResponse({
                                "error": "step_up_required",
                                "challenge_token": "..."
                            }, status=403)
                    except (InvalidOperation, ValueError, Exception):
                        # Let the view handle validation – don't block
                        pass

        return self.get_response(request)