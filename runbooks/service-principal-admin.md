# Runbook: administer SharePoint as a service principal

**Default from 2026-09-10.** Tenant changes (themes, hubs, associations, home site, and later navigation and site provisioning) are made by an app registration through `scripts/spo-admin/spo_admin.py`, not by a person clicking through the admin center or by PowerShell on a laptop. The admin center stays for inspection and for the rare thing the API cannot do.

## Why a dedicated app with a certificate

- **Graph cannot do this work.** Microsoft Graph has no API for tenant themes, hub registration, hub association, or hub navigation. Those exist only in SharePoint's own admin REST (`_api/thememanager`, `_api/HubSites`, `_api/site/JoinHubSite`, `_api/SPHSite`).
- **SharePoint REST rejects secret-based app-only tokens.** An app-only token for the SharePoint resource is accepted only when the app authenticated with a certificate. A client secret gets "Unsupported app only token".
- **Keep VillageOps least-privilege.** The VillageOps API app holds Graph `Sites.Selected` scoped to the FinanceHR site and authenticates with a secret. Widening it to tenant admin would undo that. A separate app, owned by IT, carries the tenant-wide permission.

## One-time setup, about 15 minutes

### 1. Certificate

On the Mac that will run the tool:

```bash
cd ~/sharepoint
./scripts/spo-admin/new-cert.sh tvc-spo-admin 730
```

Keep `tvc-spo-admin.pem` (private) outside the repo, for example `~/.config/tvc/tvc-spo-admin.pem`. It is gitignored either way. Put a calendar reminder two years out for renewal.

### 2. App registration

Entra admin center > App registrations > **New registration**.

| Field | Value |
|-------|-------|
| Name | `TVC SharePoint Admin (automation)` |
| Supported account types | Single tenant |
| Redirect URI | none |

Then on the app:

1. **Certificates & secrets** > Certificates > Upload `tvc-spo-admin.cer`.
2. **API permissions** > Add a permission > **SharePoint** (listed as "Office 365 SharePoint Online") > **Application permissions** > `Sites.FullControl.All` > Add. Then **Grant admin consent for fvcn**.
3. **Owners** > add IT staff. Note the **Application (client) ID** and **Directory (tenant) ID** from Overview.

No Graph permissions are needed for what this tool does. Add Graph `Sites.Selected` later only if a task needs it, and prefer that over Graph `Sites.FullControl.All`.

### 3. Local environment

```bash
python3 -m pip install --user -r scripts/spo-admin/requirements.txt

# put these in ~/.zshrc or a 1Password-backed env
export SPO_TENANT=fvcn
export SPO_TENANT_ID=<directory id>
export SPO_CLIENT_ID=<client id>
export SPO_CERT_PEM=$HOME/.config/tvc/tvc-spo-admin.pem
```

### 4. Smoke test

```bash
./scripts/spo-admin/spo_admin.py hub list
./scripts/spo-admin/spo_admin.py site get https://fvcn.sharepoint.com
```

Both read-only. Expect TVC Hub in the first, and `IsHubSite: true` in the second.

## The TVC Hub tasks

```bash
# install the brand theme tenant-wide
./scripts/spo-admin/spo_admin.py theme add --name TVC --palette theme/tvc.theme.json
./scripts/spo-admin/spo_admin.py theme list

# home site
./scripts/spo-admin/spo_admin.py home-site set https://fvcn.sharepoint.com

# associate sites with the hub (see hub-theme-and-navigation.md for the list)
for s in PottstownCampus KidsMinistry YouthMinistry YoungAdultsMin AdultMInistries WorshipArts2 \
         CounselingCenter EarlyLearningCenter TheVillageNorristown homeless.ministry \
         Communications ExternalEvents Facilities186 FinanceHR InformationTechnology OfficeAdmins \
         AV-Production SundayServices TheVillageChurch-Staff LeadershipTeam ChurchBoard; do
  ./scripts/spo-admin/spo_admin.py hub associate "https://fvcn.sharepoint.com/sites/$s" --hub https://fvcn.sharepoint.com
done
```

Applying the theme on the hub itself (Change the look) and building the hub navigation are still done in the browser on the site for now. Both have REST endpoints; they are the next things to add to the tool.

## Where this goes next

- **Key Vault.** Move the private key into Azure Key Vault and let the tool, VillageOps, or the campus agent fetch it with a managed identity. Then no laptop holds the key.
- **Run from the campus agent.** The same calls work from any Azure Function or container with access to the key. Provisioning a new campus site becomes one agent action: create the site, associate it, add the nav link.
- **Site provisioning.** Add `site create` (communication and team sites via `_api/SPSiteManager/create`) so the Fairview Campus site and future campuses are created the same way.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Unsupported app only token` | app authenticated with a secret, or SPO_CERT_PEM points at a cert without its key | use the PEM produced by `new-cert.sh` |
| `401` on `-admin` host | SharePoint `Sites.FullControl.All` not consented, or consented under Graph instead of SharePoint | check API permissions, the row must say SharePoint |
| `403 Access denied` on a site call | the site has custom permissions that exclude the app | run the call against the admin host, or grant the app on that site |
| token error `AADSTS700027` | certificate uploaded does not match the private key | re-upload the `.cer` from the same `new-cert.sh` run |
