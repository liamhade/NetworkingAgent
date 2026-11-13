"""Exceptions raised by the search API."""


class GoogleSerpError(Exception):
    """Base class for all errors raised by this package."""


class CaptchaTimeoutError(GoogleSerpError):
    """Google showed a CAPTCHA and nobody solved it in time."""
