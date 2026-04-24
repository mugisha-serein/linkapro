import structlog
import re
import logging

def scrub_pii(logger, method_name, event_dict):
    """Remove emails, phones, card patterns from log messages."""
    for key in list(event_dict.keys()):
        value = str(event_dict[key])
        # Remove emails
        value = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[EMAIL]', value)
        # Remove phone numbers (simple pattern)
        value = re.sub(r'\+\d{1,3}\d{4,14}', '[PHONE]', value)
        # Remove card-like patterns (4000-0000-0000-0000)
        value = re.sub(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b', '[CARD]', value)
        event_dict[key] = value
    return event_dict

def setup_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            scrub_pii,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )