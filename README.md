# sharepoint

Runbooks and scripts for The Village Church's SharePoint and Microsoft 365 tenant (`fvcn.sharepoint.com`).

Application code does not live here. VillageOps is in `fvcnapps/tvc-work-orders`.

## Layout

| Path | What it is |
|------|------------|
| `runbooks/` | Step-by-step procedures with the reasoning behind them. Read these first. |
| `scripts/` | PowerShell run from an admin's machine. Every script prompts before changing anything. |

## Current work

**TVC Hub** – a Communication site built at `/sites/TVCHub`, swapped into the tenant root before launch, and registered as the hub and home site. Campus sites (Fairview, Pottstown, and future campuses) associate to it.

- Runbook: `runbooks/hub-site-tvchub.md`
- Script: `scripts/TVCHub.ps1` with phases `Inspect`, `Create`, `Swap`, `Finish`

## Prerequisites for scripts

```powershell
Install-Module Microsoft.Online.SharePoint.PowerShell -Scope CurrentUser
```

SharePoint Administrator or Global Administrator role. Scripts connect to `https://fvcn-admin.sharepoint.com` and sign you in interactively.

## Conventions

- One runbook per procedure. Say why, not just what.
- Scripts are idempotent and phase-based. Read-only phases first, destructive phases behind a typed `YES`.
- Campus lists are parameters, never hardcoded, so a new campus is one more entry.
