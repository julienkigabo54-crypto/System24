"""Shared error type and input-validation helpers."""
import math
import re


class ApiError(Exception):
    """An error that is shown to the API client as clean JSON."""

    def __init__(self, message, status=400, details=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")


def require_json(payload):
    if not isinstance(payload, dict):
        raise ApiError("Request body must be a JSON object.", 400)
    return payload


def clean_text(value, field, max_len, required=True):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(f"'{field}' is required.", 400)
        return None
    if not isinstance(value, str):
        raise ApiError(f"'{field}' must be text.", 400)
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(f"'{field}' must be at most {max_len} characters.", 400)
    return value


def clean_product_id(value):
    value = clean_text(value, "product_id", 20)
    if not _ID_RE.match(value):
        raise ApiError(
            "'product_id' may contain only letters, digits, '-' and '_' (max 20 characters).", 400
        )
    return value.upper()


def _to_number(value, field):
    if isinstance(value, bool):
        raise ApiError(f"'{field}' must be a number.", 400)
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise ApiError(f"'{field}' must be a number.", 400)
    if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
        raise ApiError(f"'{field}' must be a number.", 400)
    return value


def clean_float(value, field, minimum=0.0, maximum=1e9):
    value = float(_to_number(value, field))
    if value < minimum:
        raise ApiError(f"'{field}' must be at least {minimum:g}.", 400)
    if value > maximum:
        raise ApiError(f"'{field}' is too large.", 400)
    return round(value, 2)


def clean_int(value, field, minimum=0, maximum=10_000_000):
    number = _to_number(value, field)
    if int(number) != number:
        raise ApiError(f"'{field}' must be a whole number.", 400)
    number = int(number)
    if number < minimum:
        raise ApiError(f"'{field}' must be at least {minimum}.", 400)
    if number > maximum:
        raise ApiError(f"'{field}' is too large (max {maximum}).", 400)
    return number
