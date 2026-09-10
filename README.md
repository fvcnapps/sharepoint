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
- Script: `scripts/TVCHub.ps1` with phases `Setup`, `Inspect`, `Create`, `Swap`, `Finish`

## Prerequisites for scripts

PowerShell 7.4 or later on macOS, Windows, or Linux.

```powershell
Install-Module PnP.PowerShell -Scope CurrentUser
```

The Microsoft SharePoint Online Management Shell does not sign in on macOS, so scripts here use PnP.PowerShell instead. PnP signs in through an Entra app registration in our tenant. Create it once with `./scripts/TVCHub.ps1 -Phase Setup` (Global Admin consent required) and pass the Client ID it prints to later runs, or set `$env:PNP_CLIENT_ID`.

SharePoint Administrator or Global Administrator role. Scripts connect to `https://fvcn-admin.sharepoint.com` and sign you in interactively.

## Conventions

- One runbook per procedure. Say why, not just what.
- Scripts are idempotent and phase-based. Read-only phases first, destructive phases behind a typed `YES`.
- Campus lists are parameters, never hardcoded, so a new campus is one more entry.
