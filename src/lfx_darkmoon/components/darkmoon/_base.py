"""Shared connection inputs and client helper for the Darkmoon Langflow components."""
from __future__ import annotations

from lfx.io import SecretStrInput, StrInput

from lfx_darkmoon.components.darkmoon.darkmoon_client import DarkmoonClient
from lfx_darkmoon.components.darkmoon.transport import logged_in_client


def connection_inputs():
    """Fresh connection input instances (base URL / username / password).

    Darkmoon is self-hosted, so the base URL is always supplied by the operator;
    there is no public hosted endpoint.
    """
    return [
        StrInput(
            name="base_url",
            display_name="Darkmoon base URL",
            info="Base URL of your self-hosted Darkmoon Dashboard API (FastAPI, typically port 8000).",
            required=True,
        ),
        StrInput(
            name="username",
            display_name="Dashboard username",
            info="A Darkmoon dashboard user.",
            required=True,
        ),
        SecretStrInput(
            name="password",
            display_name="Dashboard password",
            info="The dashboard user's password. Used only to obtain a short-lived JWT.",
            required=True,
        ),
    ]


class DarkmoonClientMixin:
    """Mixin that builds an authenticated Darkmoon client per run.

    This is deliberately NOT a ``Component`` subclass: each concrete component
    inherits ``(DarkmoonClientMixin, Component)`` so the extension validator
    sees exactly the four real palette components and no abstract base without a
    ``build()``/output method.

    Tests monkeypatch :func:`logged_in_client` (a module global in this file) to
    inject a mock-transport client, so component logic is exercised without a
    network.
    """

    def _client(self) -> DarkmoonClient:
        return logged_in_client(self.base_url, self.username, self.password)
