# langflow-darkmoon

[![Darkmoon](https://img.shields.io/badge/Darkmoon-autonomous%20pentest-4f46e5)](https://github.com/ASCIT31/Dark-Moon)
[![Star Dark-Moon on GitHub](https://img.shields.io/github/stars/ASCIT31/Dark-Moon?style=social)](https://github.com/ASCIT31/Dark-Moon)

[Langflow](https://github.com/langflow-ai/langflow) components for **[Darkmoon](https://github.com/ASCIT31/Dark-Moon)**, the local, privacy first autonomous AI penetration testing engine (GPLv3). Drop these into a Langflow flow to **trigger a Darkmoon pentest against a target you are authorised to assess, pull back the findings, and review the fix pull requests Darkmoon prepares**, over your own self-hosted Darkmoon Dashboard API.

> Darkmoon runs and validates security tests. It does not, and these components do not, guarantee that a system is secure. Findings can include false positives and must be reviewed by a qualified human. Only run assessments against systems you own or have explicit written authorisation to test. These components never merge a pull request; every fix is left for a person to review and merge.

## Components

| Component | Purpose |
| --- | --- |
| **Darkmoon Run Pentest** | Start a campaign against an authorised target; optionally wait and return findings and severity stats. |
| **Darkmoon Get Findings** | Return the vulnerabilities and aggregated stats for a campaign id. |
| **Darkmoon List Campaigns** | List the campaigns visible to the authenticated dashboard user. |
| **Darkmoon List Pull Requests** | List the fix pull requests Darkmoon prepared (read only), optionally scoped and filtered by state. |

## Install and load

Darkmoon is self hosted, so you point the components at your own **Darkmoon Dashboard API** (the FastAPI service shipped with Darkmoon, typically port `8000`). There is no public endpoint. Each component logs in with `POST /api/v1/auth/login` to obtain a short lived JWT.

Load the `darkmoon` directory as a Langflow components path:

```bash
pip install langflow
git clone https://github.com/ASCIT31/langflow-darkmoon
LANGFLOW_COMPONENTS_PATH=$(pwd)/langflow-darkmoon uv run langflow run
```

The four Darkmoon components then appear in the Langflow visual editor. Set the base URL, username and password on a component, and a target on **Darkmoon Run Pentest**.

## Remediation and secrets (Pro)

The Darkmoon dashboard and the remediation feature that prepares fix pull requests are paid **Pro** capabilities. The open source Darkmoon focuses on finding, proving and reporting findings locally. When remediation is enabled it needs a **credential reference**, an opaque id of a credential stored in Darkmoon's encrypted vault (created in the dashboard), not a raw token. Raw source control secrets never travel through these components, and the remediation agent only ever prepares a pull request for human review; it never merges. **Darkmoon List Pull Requests** can read those pull requests through the API.

## Privacy

Darkmoon keeps assessment work on your own infrastructure and applies a privacy gateway so the language model works over placeholders in place of your real hosts, IPs and credentials. These components send data only to the base URL you configure.

## Darkmoon at a glance

Darkmoon is a GPLv3, self-hosted autonomous AI pentester: 50 specialist agents and 140+ tools exposed over MCP, running against targets you are authorised to test. See [ASCIT31/Dark-Moon](https://github.com/ASCIT31/Dark-Moon).

## Development

```bash
pip install "lfx" pytest
pytest -q
```

The API client (`darkmoon/darkmoon_client.py`) is dependency free and transport injected, so its logic is unit tested without a network (mock transport). The component tests instantiate the real Langflow (`lfx`) components, inject a mock transport, run each output, and assert each builds a valid Langflow frontend node. A full end to end run additionally requires a running Darkmoon instance pointed at an authorised target.

## Related integrations

Darkmoon also ships integrations for [n8n](https://github.com/ASCIT31/n8n-nodes-darkmoon), [Activepieces](https://github.com/ASCIT31/activepieces-piece-darkmoon), [Dify](https://github.com/ASCIT31/dify-plugin-darkmoon), [LangChain](https://github.com/ASCIT31/langchain-darkmoon) and [GitHub Actions](https://github.com/ASCIT31/darkmoon-scan-action).

## License

MIT, see [LICENSE](./LICENSE). Not affiliated with Langflow; "Langflow" is a trademark of its respective owner.
