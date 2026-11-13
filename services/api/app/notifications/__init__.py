"""Outbound notifications (SMS today, e-mail later).

Nothing outside this package talks to a messaging provider directly, so swapping
FarazSMS for Kavenegar is a new function here and a settings value.
"""

from app.notifications.sms import send_otp

__all__ = ["send_otp"]
