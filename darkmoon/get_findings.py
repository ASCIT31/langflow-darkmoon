from __future__ import annotations

from lfx.io import MessageTextInput, Output
from lfx.schema.data import Data

from ._base import DarkmoonComponentBase, connection_inputs


class DarkmoonGetFindingsComponent(DarkmoonComponentBase):
    """Return the vulnerabilities and aggregated stats for a Darkmoon campaign."""

    display_name = "Darkmoon Get Findings"
    description = "Return the vulnerabilities and aggregated stats for a Darkmoon campaign id."
    icon = "darkmoon"
    name = "DarkmoonGetFindings"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="campaign_id",
            display_name="Campaign id",
            info="The Darkmoon campaign id, e.g. camp_20260922_abc123.",
            required=True,
        ),
    ]

    outputs = [Output(display_name="Findings", name="findings", method="get_findings_action")]

    def get_findings_action(self) -> Data:
        campaign_id = str(self.campaign_id or "").strip()
        if not campaign_id:
            raise ValueError("A campaign id is required.")
        findings = self._client().get_findings(campaign_id)
        data = Data(
            data={
                "campaign_id": campaign_id,
                "total": findings["total"],
                "stats": findings["stats"],
                "findings": findings["data"],
            }
        )
        self.status = data
        return data
