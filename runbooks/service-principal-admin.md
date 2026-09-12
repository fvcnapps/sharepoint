# Runbook: administer SharePoint as a service principal

**Default from 2026-09-10.** Tenant changes (themes, hubs, associations, home site, and later navigation and site provisioning) are made by an app registration through `scripts/spo-admin/spo_admin.py`, not by a person clicking through the admin center or by PowerShell on a laptop. The admin center stays for inspection and for the rare thing the API cannot do.

## Why a dedicated app with a certificate

- **Graph cannot do this work.** Microsoft Graph has no API for tenant themes, hub registration, hub association, or hub navigation. Those exist only in SharePoint's own admin REST (`_api/thememanager`, `_api/HubSites`, `_api/site/JoinHubSite`, `_api/SPHSite`).
- **SharePoint REST rejects secret-based app-only tokens.** An app-only token for the SharePoint resource is accepted only when the app authenticated with a certificate. A client secret gets "Unsupported app only token".
- **Keep VillageOps least-privilege.** The VillageOps API app holds Graph `Sites.Selected` scoped to the FinanceHR site and authenticates with a secret. Widening it to tenant admin would undo that. A separate app, owned by IT, carries the tenant-wide permission.

## One-time setup, about 15 minutes

Done 2026-09-11 with the Azure CLI already signed in as a Global Administrator. The Entra portal steps are the fallback if `az` is not available.

| Item | Value |
|------|-------|
| App registration | `TVC SharePoint Admin (automation)` |
| Application (client) ID | `3297a6e3-1f15-47b8-9dad-9b8399a61186` |
| Service principal object ID | `2acd1212-361a-4cf1-802c-52aebfc7d34e` |
| Directory (tenant) ID | `ca740557-37f4-4764-bcce-b116c7af3629` |
| Certificate thumbprint | `8D847780FDBB8FA368BC2934357AEF343AA09B2A` |
| Certificate expires | 2028-09-11 (renew by 2028-08-01) |
| Permission | SharePoint `Sites.FullControl.All`, application, admin consent granted |
| Owner | micah.roemmich@fvcn.org |
| Private key | `~/.config/tvc/tvc-spo-admin.pem` on Micah's Mac, mode 600 |
| Environment | `~/.config/tvc/spo-admin.env`, sourced from `~/.zshrc` |

### 1. Certificate

On the Mac that will run the tool:

```bash
mkdir -p ~/.config/tvc && chmod 700 ~/.config/tvc && cd ~/.config/tvc
bash ~/sharepoint/scripts/spo-admin/new-cert.sh tvc-spo-admin 730
```

Keep `tvc-spo-admin.pem` (private) outside the repo. It is gitignored either way. Put a calendar reminder two years out for renewal.

### 2. App registration with the Azure CLI

```bash
az ad app create --display-name "TVC SharePoint Admin (automation)" --sign-in-audience AzureADMyOrg
APP=<appId from above>
az ad sp create --id $APP
az ad app owner add --id $APP --owner-object-id $(az ad signed-in-user show --query id -o tsv)

# certificate: pass --end-date or the CLI stamps a one-year expiry on a two-year cert
END=$(openssl x509 -in ~/.config/tvc/tvc-spo-admin.crt -noout -enddate | sed 's/notAfter=//')
az ad app credential reset --id $APP --cert "@$HOME/.config/tvc/tvc-spo-admin.crt" --append \
  --end-date "$(date -j -f '%b %d %T %Y %Z' "$END" '+%Y-%m-%dT%H:%M:%SZ')"

# SharePoint (resource app 00000003-0000-0ff1-ce00-000000000000) > Sites.FullControl.All, application
ROLE=$(az ad sp show --id 00000003-0000-0ff1-ce00-000000000000 --query "appRoles[?value=='Sites.FullControl.All'].id" -o tsv)
az ad app permission add --id $APP --api 00000003-0000-0ff1-ce00-000000000000 --api-permissions $ROLE=Role
az ad app permission admin-consent --id $APP
```

Verify consent landed (it can take a minute; if the list stays empty, POST the appRoleAssignment through Graph):

```bash
SP=$(az ad sp show --id $APP --query id -o tsv)
az rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$SP/appRoleAssignments" --query "value[].resourceDisplayName"
```

Portal equivalent: Entra admin center > App registrations > New registration (single tenant, no redirect URI) > Certificates & secrets > upload the `.cer` > API permissions > SharePoint > Application > `Sites.FullControl.All` > Grant admin consent > Owners.

No Graph permissions are needed for what this tool does. Add Graph `Sites.Selected` later only if a task needs it, and prefer that over Graph `Sites.FullControl.All`.

### 3. Local environment

Homebrew Python refuses `pip install --user`, so the repo uses a virtualenv (`.venv/` is gitignored):

```bash
cd ~/sharepoint
python3 -m venv .venv && .venv/bin/pip install -r scripts/spo-admin/requirements.txt

cat > ~/.config/tvc/spo-admin.env <<'EOF'
export SPO_TENANT=fvcn
export SPO_TENANT_ID=ca740557-37f4-4764-bcce-b116c7af3629
export SPO_CLIENT_ID=3297a6e3-1f15-47b8-9dad-9b8399a61186
export SPO_CERT_PEM=$HOME/.config/tvc/tvc-spo-admin.pem
EOF
chmod 600 ~/.config/tvc/spo-admin.env
echo '[ -f ~/.config/tvc/spo-admin.env ] && source ~/.config/tvc/spo-admin.env' >> ~/.zshrc
```

Run the tool as `.venv/bin/python scripts/spo-admin/spo_admin.py ...` or activate the venv first. The examples below assume the venv is active.

### 4. Smoke test

```bash
./scripts/spo-admin/spo_admin.py hub list
./scripts/spo-admin/spo_admin.py site get https://fvcn.sharepoint.com
```

Both read-only. Expect TVC Hub in the first, and `IsHubSite: true` in the second. Both passed on the first run, 2026-09-11.

## The TVC Hub tasks

```bash
# install the brand theme tenant-wide
./scripts/spo-admin/spo_admin.py theme add --name TVC --palette theme/tvc.theme.json
./scripts/spo-admin/spo_admin.py theme list

# home site (SPHSite/SetSPHSite takes siteUrl; read it back with SPO.Tenant/GetSPHSiteUrl)
./scripts/spo-admin/spo_admin.py home-site set https://fvcn.sharepoint.com
./scripts/spo-admin/spo_admin.py home-site get

# associate sites with the hub (see hub-theme-and-navigation.md for the list)
for s in PottstownCampus KidsMinistry YouthMinistry YoungAdultsMin AdultMInistries WorshipArts2 \
         CounselingCenter EarlyLearningCenter TheVillageNorristown homeless.ministry \
         Communications ExternalEvents Facilities186 FinanceHR InformationTechnology OfficeAdmins \
         AV-Production SundayServices TheVillageChurch-Staff LeadershipTeam ChurchBoard; do
  ./scripts/spo-admin/spo_admin.py hub associate "https://fvcn.sharepoint.com/sites/$s" --hub https://fvcn.sharepoint.com
done
```

All of the above ran successfully on 2026-09-11. Applying the theme and header on the hub and building the hub navigation are also REST calls; see `hub-theme-and-navigation.md` for the commands.

## REST shapes verified live, 2026-09-11

Recorded so nobody has to rediscover them. Host is `https://fvcn.sharepoint.com` unless marked admin.

| Task | Call | Note |
|------|------|------|
| Home site set | admin `POST /_api/SPHSite/SetSPHSite` `{"siteUrl": ...}` | `sphSiteUrl` (the CSOM name) is rejected. Returns the site id. |
| Home site read | admin `GET /_api/SPO.Tenant/GetSPHSiteUrl` | `SPHSite/Details` returns null even when set. |
| Tenant theme add | admin `POST /_api/thememanager/AddTenantTheme` `{"name","themeJson"}` | returns `{"value": true}`. `GetTenantThemingOptions` returns null when no custom theme exists. |
| Theme apply on a site | `POST /_api/thememanager/ApplyTheme` same body | returns the themed catalog path; `HubSiteData.themeKey` picks up the hash. |
| Header, menu, footer, audience flags | `POST /_api/web` with `X-HTTP-Method: MERGE`, `IF-MATCH: *` | `HeaderLayout` 2 = Compact, `HeaderEmphasis` 3 = Strong, `MegaMenuEnabled`, `NavAudienceTargetingEnabled`, `FooterEnabled`. |
| Site logo | upload PNG to `/SiteAssets`, then `POST /_api/siteiconmanager/setsitelogo` `{"relativeLogoUrl","type":0,"aspect":N}` | aspect 1 = rectangular header logo (stored in web property `RectSiteLogoUrl`); aspect 0 = square thumbnail (`SiteLogoUrl`). |
| Hub navigation | `POST /_api/web/navigation/TopNavigationBar` and `.../GetNodeById(id)/Children` | The hub web's top navigation bar **is** the hub navigation; `GET /_api/web/HubSiteData` reflects it. Nodes carry `AudienceIds`. |
| Hub navigation writes | `POST /_api/navigation/SaveMenuState` on `menuNodeKey='1002'` (what the nav editor uses); MERGE and DELETE on `/_api/web/navigation/GetNodeById(id)` | `GetNodeById(id)/Children` POST rejects links to other site collections with a 500 "no such file or folder"; SaveMenuState accepts them and carries `AudienceIds` and `OpenInNewWindow`. Omitting a node from a saved state does not delete it. |
| Footer title | `GET /_api/navigation/MenuState?menuNodeKey='13b7c916-4fea-4bb2-8994-5cf274aeb530'`, written with `SaveMenuState` | from PnP.Framework `NavigationExtensions.cs`; the `mapProviderName` form is wrong for the footer. |
| Hub record (logo, title, description) | admin `POST /_api/HubSites/GetById('{id}')` MERGE `{"LogoUrl","Title","Description"}` | site-level `HubSiteData` catches up within minutes. `isNavAudienceTargeted` there has no setter; it flips once the web flag is on and a nav write has happened. |
| Site create (no group) | `POST /_api/SPSiteManager/create` `{"request":{Title,Url,Lcid,ShareByEmailEnabled,Description,WebTemplate,SiteDesignId,WebTemplateExtensionId,Owner,HubSiteId}}`; status `GET /_api/SPSiteManager/status?url='…'` | implemented, dry-run only so far. |
| Group-connected site | `POST /_api/GroupSiteManager/CreateGroupEx` | **403 app-only**: SharePoint calls Entra as the app, which has no group permission. Create the group through Graph as a signed-in admin instead (`hub-theme-and-navigation.md`, Adding a campus). |
| Tenant site lookup | admin `POST /_api/SPO.Tenant/GetSitePropertiesFromSharePointByFilters` `{"speFilter":{"IncludePersonalSite":0,"IncludeDetail":true,"Filter":"Url -like 'Archive'"}}` | `GET /_api/SPO.Tenant/sites` is not supported. Found the real archive URL of the classic root. |
| Hub association | `POST {site}/_api/site/JoinHubSite('{hubId}')` | worked for all 22 sites, no throttling. |

## Where this goes next

- **Key Vault.** Move the private key into Azure Key Vault and let the tool, VillageOps, or the campus agent fetch it with a managed identity. Then no laptop holds the key.
- **Run from the campus agent.** The same calls work from any Azure Function or container with access to the key. Provisioning a new campus site becomes one agent action: create the site, associate it, add the nav link.
- **Group-connected site provisioning app-only.** `site create` covers communication and plain team sites. Campus sites are group-connected, which needs Graph `Group.Create` on the app before it can run without a person.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Unsupported app only token` | app authenticated with a secret, or SPO_CERT_PEM points at a cert without its key | use the PEM produced by `new-cert.sh` |
| `401` on `-admin` host | SharePoint `Sites.FullControl.All` not consented, or consented under Graph instead of SharePoint | check API permissions, the row must say SharePoint |
| `403 Access denied` on a site call | the site has custom permissions that exclude the app | run the call against the admin host, or grant the app on that site |
| token error `AADSTS700027` | certificate uploaded does not match the private key | re-upload the `.cer` from the same `new-cert.sh` run |
| token error `AADSTS7000222` after a year | `az ad app credential reset` defaulted the credential to one year | re-upload with `--end-date` matching the certificate |
| `admin-consent` prints nothing and the app role list is empty | Graph propagation lag, or the command silently failed | wait a minute and re-check; if still empty, POST `servicePrincipals/{sp}/appRoleAssignments` with `resourceId` = SharePoint SP object id and `appRoleId` = `678536fe-1083-478a-9c59-b99265e6b0d3` |
