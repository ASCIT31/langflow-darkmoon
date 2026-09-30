"""lfx-darkmoon: Darkmoon components as a standalone Langflow Extension Bundle.

This package is the distribution unit ``lfx-darkmoon``. At runtime Langflow's
loader discovers the ``extension.json`` shipped alongside this ``__init__.py``
and registers the four Darkmoon components under namespaced IDs such as
``ext:darkmoon:DarkmoonRunPentest@official``.

Darkmoon is the local, privacy-first autonomous AI penetration testing engine
(GPLv3): https://github.com/ASCIT31/Dark-Moon. These components talk to a
self-hosted Darkmoon Dashboard API; there is no public hosted endpoint.
"""

from lfx_darkmoon.components.darkmoon import (
    DarkmoonGetFindingsComponent,
    DarkmoonListCampaignsComponent,
    DarkmoonListPullRequestsComponent,
    DarkmoonRunPentestComponent,
)

__all__ = [
    "DarkmoonRunPentestComponent",
    "DarkmoonGetFindingsComponent",
    "DarkmoonListCampaignsComponent",
    "DarkmoonListPullRequestsComponent",
]
