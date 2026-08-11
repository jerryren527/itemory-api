import base64

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailAPIBackend(BaseEmailBackend):
    """Sends mail through the Gmail API over HTTPS instead of SMTP.

    Railway blocks outbound SMTP, so the SMTP-based backend hangs until the
    worker is killed. This backend uses a long-lived OAuth refresh token
    (minted once via a local consent flow) to call Gmail's REST API instead.
    """

    def _get_access_token(self):
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GMAIL_API_CLIENT_ID,
                "client_secret": settings.GMAIL_API_CLIENT_SECRET,
                "refresh_token": settings.GMAIL_API_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        if not response.ok:
            raise RuntimeError(f"Gmail token refresh failed ({response.status_code}): {response.text}")
        return response.json()["access_token"]

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        access_token = self._get_access_token()
        sent_count = 0

        for message in email_messages:
            # message.message() builds the full MIME tree (plain body, HTML
            # alternatives, inline/attached files, headers) the same way
            # Django's SMTP backend would send it, so HTML emails and inline
            # images (e.g. the verification email's logo) aren't dropped.
            mime_message = message.message()

            raw = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("ascii")

            try:
                response = requests.post(
                    SEND_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"raw": raw},
                    timeout=10,
                )
                response.raise_for_status()
                sent_count += 1
            except requests.RequestException:
                if not self.fail_silently:
                    raise

        return sent_count
