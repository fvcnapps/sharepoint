# Runbook: Create the TVC Hub site at /sites/TVCHub

**Goal:** A Communication site named **TVC Hub**, built at `https://fvcn.sharepoint.com/sites/TVCHub` and then swapped into the tenant root (`https://fvcn.sharepoint.com`) before launch. The root is registered as the hub and home site so each campus site (Fairview, Pottstown, and future campuses) associates to it.

**Script:** `scripts/TVCHub.ps1` runs every step below in four phases (`Inspect`, `Create`, `Swap`, `Finish`) with confirmation prompts. The manual steps are kept here for reference.

**Order matters.** Do not register `/sites/TVCHub` as a hub before the swap. `Invoke-SPOSiteSwap` refuses a source that is a hub or associated with one.

**Symptom this fixes:** Browsing to or creating `/sites/TVCHub` bounces to the old classic site.

## Why it redirects

Three things cause that behavior. Check them in order; the first one that matches is the fix.

| # | Cause | How to confirm | Fix |
|---|-------|----------------|-----|
| 1 | A **redirect stub** already lives at `/sites/TVCHub` (template `REDIRECTSITE#0`). SharePoint leaves one behind whenever a site is renamed or its URL changes. | `Get-SPOSite -Identity https://fvcn.sharepoint.com/sites/TVCHub \| Select Url, Template, Status` shows `REDIRECTSITE#0`. | `Remove-SPOSite` then `Remove-SPODeletedSite` (see below). |
| 2 | A **deleted site** is still holding the URL in the recycle bin (93-day hold). | Admin center > Sites > **Deleted sites**, or `Get-SPODeletedSite`. | Permanently delete it from Deleted sites, or `Remove-SPODeletedSite`. |
| 3 | **Site creation is routed to a custom form** or disabled, so the "+ Create site" button on the SharePoint start page lands on the classic site. | Admin center > Settings > **Site creation** shows "Use the form at this URL" or users are not allowed to create sites. | Create from **Active sites > Create** in the admin center instead. That path ignores the custom form. |

## If the admin center says the site does not exist

- **Redirect stubs are hidden from the Active sites list.** Only `Get-SPOSite -Identity <url>` shows them. Run that command before concluding the URL is free.
- **A missing site returns a 404, never a redirect.** If browsing to `/sites/TVCHub` lands on the classic site, the bounce is happening in the *Create site* flow, not at the URL. Check admin center > Settings > **Site creation**: clear "Use the form at this URL" and make sure the default path is `/sites/`. Or bypass the start page entirely by creating from **Active sites > Create** or with `New-SPOSite` below.
- **The tenant root is separate.** `fvcn.sharepoint.com` with no path is the root site. If that is the classic site, landing there is expected and does not block creating `/sites/TVCHub`. Replacing the root is the Swap phase below.

## Steps

Run in PowerShell (5.1 or 7) as a SharePoint Administrator or Global Administrator.

```powershell
Install-Module Microsoft.Online.SharePoint.PowerShell -Scope CurrentUser
Connect-SPOService -Url https://fvcn-admin.sharepoint.com

# 1. What is sitting at the URL right now?
Get-SPOSite -Identity https://fvcn.sharepoint.com/sites/TVCHub | Select Url, Template, Status
Get-SPODeletedSite | Where-Object Url -like "*TVCHub*"

# 2. Clear it if it is a redirect stub or a deleted site.
#    Skip Remove-SPOSite if the first command above returned "not found".
Remove-SPOSite        -Identity https://fvcn.sharepoint.com/sites/TVCHub -NoWait
Remove-SPODeletedSite -Identity https://fvcn.sharepoint.com/sites/TVCHub

# 3. Create the Communication site.
New-SPOSite -Url https://fvcn.sharepoint.com/sites/TVCHub `
            -Title "TVC Hub" `
            -Owner micah.roemmich@fvcn.org `
            -Template "SITEPAGEPUBLISHING#0" `
            -StorageQuota 1024

```

Build the hub content, theme, and navigation at `/sites/TVCHub`. Staff can review it there while the classic root keeps working.

## Swap the root (before launch)

```powershell
# Preconditions the swap enforces:
#   - source is a communication site, not a hub, not associated with a hub
#   - target (root) is not a hub; unregister it first if it is
#   - archive URL does not exist, active or deleted
Get-SPOSite -Identity https://fvcn.sharepoint.com | Select IsHubSite, HubSiteId, Template
Unregister-SPOHubSite -Identity https://fvcn.sharepoint.com          # only if IsHubSite is True

Invoke-SPOSiteSwap -SourceUrl  https://fvcn.sharepoint.com/sites/TVCHub `
                   -TargetUrl  https://fvcn.sharepoint.com `
                   -ArchiveUrl https://fvcn.sharepoint.com/sites/ClassicRoot-Archive
```

What happens:

- `/sites/TVCHub` becomes the root. A redirect is left at `/sites/TVCHub` pointing to the root (add `-DisableRedirect` if you want that URL free for something else).
- The old classic root moves to `/sites/ClassicRoot-Archive`. It is often left in a `NoAccess` lock. Unlock it so staff can still reach old content: `Set-SPOSite -Identity <archive url> -LockState Unlock`.
- Both sites are unavailable for several minutes. Schedule it off-hours, never Sunday morning.
- Links to pages and files that lived on the old root break. Search, Recent, and Followed sites catch up over a day or so. Audit Teams tabs, Planning Center links, and email signatures that point at `fvcn.sharepoint.com/...` paths.

The admin center also offers this under Active sites > select the root > **Replace site**, but only when the tenant has fewer than 10,000 sites. PowerShell works regardless.

## Finish: hub, home site, campuses

```powershell
Register-SPOHubSite -Site https://fvcn.sharepoint.com -Principals $null
Set-SPOHomeSite     -HomeSiteUrl https://fvcn.sharepoint.com

# Repeat per campus as we grow.
Add-SPOHubSiteAssociation -Site https://fvcn.sharepoint.com/sites/Fairview  -HubSite https://fvcn.sharepoint.com
Add-SPOHubSiteAssociation -Site https://fvcn.sharepoint.com/sites/Pottstown -HubSite https://fvcn.sharepoint.com
```

Replace the campus URLs with the real ones. Get them from `Get-SPOSite -Limit All | Select Url, Title`.

Setting the home site gives the hub the **Home** button in the SharePoint app bar and makes it the Viva Connections landing page in Teams.

## Without PowerShell

1. SharePoint admin center > Sites > **Deleted sites**. If TVCHub is listed, select it and **Delete permanently**.
2. Sites > **Active sites** > **Create** > **Communication site** > Topic. Name `TVC Hub`, site address `TVCHub`. Fix the language and time zone before saving; they cannot be changed later.
3. Build the site. Do not register it as a hub yet.
4. Active sites > select the **root** site > **Replace site** > choose TVC Hub, give an archive URL.
5. Active sites > select the new root > **Hub** > **Register as hub site**. Settings > **Home site** > set the root.
6. Open each campus site > Settings gear > **Site information** > Hub site association > TVC Hub.

## After launch

- Apply the brand theme to the hub. Associated sites inherit its theme and top navigation.
- Hub navigation should list campuses, not departments, so a third campus is one more link.
- Wait to hand out the URL until the old classic site's owners know traffic is moving. Set a banner or a redirect on the classic site pointing to the hub once content has moved.

## Does this affect VillageOps?

No. VillageOps (repo `fvcnapps/tvc-work-orders`) delivers receipts and reports to the FinanceHR site by site ID, not to the root. The root swap does not touch it.
