from __future__ import annotations

from lfx.io import Output
from lfx.schema.data import Data

from ._base import DarkmoonComponentBase, connection_inputs


class DarkmoonListCampaignsComponent(DarkmoonComponentBase):
    """Return the campaigns visible to the authenticated dashboard user."""

    display_name = "Darkmoon List Campaigns"
    description = "List the Darkmoon campaigns visible to the authenticated dashboard user."
    icon = "darkmoon"
    name = "DarkmoonListCampaigns"

    inputs = [*connection_inputs()]

    outputs = [Output(display_name="Campaigns", name="campaigns", method="list_campaigns_action")]

    def list_campaigns_action(self) -> Data:
        campaigns = self._client().list_campaigns()
        data = Data(data={"total": len(campaigns), "campaigns": campaigns})
        self.status = data
        return data
