from __future__ import annotations

from lfx.io import DropdownInput, MessageTextInput, Output
from lfx.schema.data import Data

from ._base import DarkmoonComponentBase, connection_inputs
from .darkmoon_client import DarkmoonClient, PR_STATES


class DarkmoonListPullRequestsComponent(DarkmoonComponentBase):
    """Return the fix pull requests Darkmoon prepared (read-only).

    Pull requests are prepared by the paid Pro remediation feature and left for a
    human to review and merge. This component only reads them; it never merges.
    """

    display_name = "Darkmoon List Pull Requests"
    description = "List the fix pull requests Darkmoon prepared (read-only)."
    icon = "darkmoon"
    name = "DarkmoonListPullRequests"

    inputs = [
        *connection_inputs(),
        MessageTextInput(
            name="campaign_id",
            display_name="Campaign id",
            info="Optional campaign id to scope the pull requests to (the only server-side filter).",
            advanced=True,
        ),
        DropdownInput(
            name="state",
            display_name="State",
            options=["", *PR_STATES],
            value="",
            advanced=True,
        ),
    ]

    outputs = [Output(display_name="Pull Requests", name="pull_requests", method="list_pull_requests_action")]

    def list_pull_requests_action(self) -> Data:
        campaign_id = str(self.campaign_id or "").strip() or None
        client = self._client()
        prs = client.list_pull_requests(campaign_id)
        state = str(self.state or "").strip()
        if state:
            prs = DarkmoonClient.filter_pull_requests(prs, state=[state])
        data = Data(data={"total": len(prs), "pull_requests": prs})
        self.status = data
        return data
