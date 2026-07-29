VENDOR_PROFILE = "vendor_profile"
SERVICE_PACKAGE = "service_package"
PORTFOLIO_MEDIA = "portfolio_media"
USER_ACCOUNT = "user_account"

APPROVE = "approve"
REJECT = "reject"
SUSPEND = "suspend"
REINSTATE = "reinstate"
BAN = "ban"
HARD_DELETE = "hard_delete"

TRUST_AND_SAFETY_GUIDELINE = "Marketplace trust and safety"
QUALITY_GUIDELINE = "Marketplace content quality"
ACCOUNT_SAFETY_GUIDELINE = "Platform safety and community conduct"


_POLICY_DEFAULTS = {
    (VENDOR_PROFILE, APPROVE): (
        "vendor_profile_approve",
        "Vendor profile approved because it meets marketplace trust and review requirements.",
        TRUST_AND_SAFETY_GUIDELINE,
    ),
    (VENDOR_PROFILE, REJECT): (
        "vendor_profile_reject",
        "Vendor profile rejected because required business information is incomplete, unclear, or does not meet marketplace trust requirements.",
        TRUST_AND_SAFETY_GUIDELINE,
    ),
    (VENDOR_PROFILE, SUSPEND): (
        "vendor_profile_suspend",
        "Vendor profile suspended because the account requires further review under marketplace trust and safety guidelines.",
        TRUST_AND_SAFETY_GUIDELINE,
    ),
    (VENDOR_PROFILE, REINSTATE): (
        "vendor_profile_reinstate",
        "Vendor profile reinstated after review confirmed the account can return to marketplace access.",
        TRUST_AND_SAFETY_GUIDELINE,
    ),
    (SERVICE_PACKAGE, APPROVE): (
        "service_package_approve",
        "Package approved because the service offer meets marketplace review requirements.",
        QUALITY_GUIDELINE,
    ),
    (SERVICE_PACKAGE, REJECT): (
        "service_package_reject",
        "Package rejected because the service offer is incomplete, unclear, or does not provide enough detail for planners to evaluate it safely.",
        QUALITY_GUIDELINE,
    ),
    (SERVICE_PACKAGE, HARD_DELETE): (
        "service_package_hard_delete",
        "Content permanently removed because it violates marketplace quality, safety, or administrative integrity requirements.",
        QUALITY_GUIDELINE,
    ),
    (PORTFOLIO_MEDIA, APPROVE): (
        "portfolio_media_approve",
        "Portfolio item approved because the uploaded media meets marketplace quality, relevance, and trust standards.",
        QUALITY_GUIDELINE,
    ),
    (PORTFOLIO_MEDIA, REJECT): (
        "portfolio_media_reject",
        "Portfolio item rejected because the uploaded media does not meet marketplace quality, relevance, or trust standards.",
        QUALITY_GUIDELINE,
    ),
    (PORTFOLIO_MEDIA, HARD_DELETE): (
        "portfolio_media_hard_delete",
        "Content permanently removed because it violates marketplace quality, safety, or administrative integrity requirements.",
        QUALITY_GUIDELINE,
    ),
    (USER_ACCOUNT, BAN): (
        "user_account_ban",
        "User account disabled because activity requires restriction under platform safety and community guidelines.",
        ACCOUNT_SAFETY_GUIDELINE,
    ),
    (USER_ACCOUNT, REINSTATE): (
        "user_account_reinstate",
        "User account reinstated after review confirmed access can be restored under platform safety guidelines.",
        ACCOUNT_SAFETY_GUIDELINE,
    ),
}


def generate_governance_reason(
    *,
    target_type: str,
    action: str,
    target=None,
    admin_reason: str | None = None,
) -> dict:
    policy_code, system_reason, community_guideline = _POLICY_DEFAULTS.get(
        (target_type, action),
        (
            f"{target_type}_{action}",
            "Action completed under marketplace trust, safety, and administrative integrity requirements.",
            TRUST_AND_SAFETY_GUIDELINE,
        ),
    )
    reason = (admin_reason or "").strip()
    return {
        "reason": reason or system_reason,
        "policy_code": policy_code,
        "source": "admin" if reason else "system",
        "community_guideline": community_guideline,
    }


def policy_reason_audit_details(reason: dict, extra: dict | None = None) -> dict:
    details = {
        "reason": reason["reason"],
        "policy_code": reason["policy_code"],
        "reason_source": reason["source"],
        "community_guideline": reason["community_guideline"],
    }
    if extra:
        details.update(extra)
    return details
