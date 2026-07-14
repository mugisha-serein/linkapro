from __future__ import annotations

import hashlib
import json

from domain.vendors.inquiries.entity import Inquiry
from domain.vendors.inquiries.rules import ensure_vendor_can_receive_inquiry
from domain.vendors.shared.pagination import PageRequest
from application.vendors.inquiries.commands import MarkInquiryReadCommand, SendInquiryCommand
from application.vendors.inquiries.dtos import InquiryDTO
from application.vendors.inquiries.queries import ListInquiriesQuery
from application.vendors.shared.dtos import PageDTO


class InquiryCommandHandlersMixin:
        def send_inquiry(self, cmd: SendInquiryCommand) -> InquiryDTO:
            payload_digest = self._inquiry_payload_digest(cmd)

            def operation() -> InquiryDTO:
                self._assert_inquiry_allowed(
                    requester_identity=cmd.requester_id,
                    vendor_id=cmd.vendor_id,
                    payload_digest=payload_digest,
                )
                profile = self.vendor_repo.get_by_id(cmd.vendor_id)
                ensure_vendor_can_receive_inquiry(profile)
                inquiry = Inquiry.create(
                    vendor_id=cmd.vendor_id,
                    client_name=cmd.client_name,
                    client_email=cmd.client_email,
                    client_phone=cmd.client_phone,
                    message=cmd.message,
                    event_date=cmd.event_date,
                )
                saved = self._add_with_pending_events(inquiry)
                return self._to_inquiry_dto(saved)

            return self._run_required_idempotent(
                "vendor_inquiry.send", cmd.requester_id, cmd.idempotency_key, cmd, operation
            )

        def mark_inquiry_read(self, cmd: MarkInquiryReadCommand) -> InquiryDTO:
            return self._execute_transition(
                authorize=lambda: self._assert_actor_owns_vendor(cmd.actor, cmd.vendor_id),
                loader=lambda: self._get_inquiry_or_raise(cmd.vendor_id, cmd.inquiry_id),
                expected_version=cmd.expected_version,
                transition=lambda inquiry: inquiry.mark_read(),
                to_dto=self._to_inquiry_dto,
            )


class InquiryQueryHandlersMixin:
        def list_inquiries(self, query: ListInquiriesQuery) -> PageDTO[InquiryDTO]:
            self._assert_actor_can_access_vendor(query)
            page = query.page or PageRequest()
            if query.search_text:
                inquiries = self.inquiry_repo.search(
                    query.vendor_id,
                    query.search_text,
                    None,
                    None,
                    page,
                )
            else:
                inquiries = self.inquiry_repo.list_by_vendor(query.vendor_id, page)
            return self._map_page(inquiries, self._to_inquiry_dto)
