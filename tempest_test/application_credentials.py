"""application_credentials.py
Provides OAuth2 implementation for Tempest Test integration without user input.
"""

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from .const import AUTHORIZE_URL, TOKEN_URL

# Hard‑coded OAuth2 credentials for Tempest Test integration
CLIENT_ID = "9a14f12b-15f6-4843-b7b4-07e5418a3888"


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> LocalOAuth2Implementation:
    """Return a LocalOAuth2Implementation with embedded client ID and secret."""
    server = AuthorizationServer(
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
    )
    return LocalOAuth2Implementation(
        hass,
        auth_domain,
        CLIENT_ID,
        server.authorize_url,
        server.token_url,
    )
