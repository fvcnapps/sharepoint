# Runbook: Create the TVC Hub site at /sites/TVCHub

**Goal:** A Communication site named **TVC Hub**, built at `https://fvcn.sharepoint.com/sites/TVCHub` and then swapped into the tenant root (`https://fvcn.sharepoint.com`) before launch. The root is registered as the hub and home site so each campus site (Fairview, Pottstown, and future campuses) associates to it.

**Browser first.** The section *Browser path* below does everything in the SharePoint admin center. **Script:** `scripts/TVCHub.ps1` runs the same steps in phases (`Setup`, `Inspect`, `Create`, `Swap`, `Finish`) with confirmation prompts. It uses PnP.PowerShell so it works from a Mac. The manual commands below use Microsoft's SharePoint Online Management Shell, which only signs in on Windows; each has a PnP equivalent (`Get-PnPTenantSite`, `Invoke-PnPSiteSwap`, `Register-PnPHubSite`, and so on) that the script uses.

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

Run in Windows PowerShell as a SharePoint Administrator or Global Administrator. On a Mac, use the script instead.

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
- The old classic root moves to the archive URL. **The admin center's Replace site ignores the name you type and picks its own**: ours landed at `/sites/archive-2026-09-10T171521Z` (UTC timestamp of the swap). Only PowerShell honours `-ArchiveUrl`. Confirm the real URL afterwards with the tenant filter call in `service-principal-admin.md`. It is often left in a `NoAccess` lock; ours came out `Unlock`. If not: `Set-SPOSite -Identity <archive url> -LockState Unlock`.
- Both sites are unavailable for several minutes. Schedule it off-hours, never Sunday morning.
- Links to pages and files that lived on the old root break. Search, Recent, and Followed sites catch up over a day or so. Audit Teams tabs, Planning Center links, and email signatures that point at `fvcn.sharepoint.com/...` paths.

The admin center also offers this under Active sites > select the root > **Replace site**, but only when the tenant has fewer than 10,000 sites. PowerShell works regardless.

## Finish: hub, home site, campuses

```powershell
Register-SPOHubSite -Site https://fvcn.sharepoint.com -Principals $null
Set-SPOHomeSite     -HomeSiteUrl https://fvcn.sharepoint.com

# Repeat per campus as we grow.
Add-SPOHubSiteAssociation -Site https://fvcn.sharepoint.com/sites/FairviewCampus  -HubSite https://fvcn.sharepoint.com   # create this site first
Add-SPOHubSiteAssociation -Site https://fvcn.sharepoint.com/sites/PottstownCampus -HubSite https://fvcn.sharepoint.com
```

Pottstown's site is `/sites/PottstownCampus`. Fairview has no campus site yet; see the tenant snapshot below.

Setting the home site gives the hub the **Home** button in the SharePoint app bar and makes it the Viva Connections landing page in Teams.

## Browser path (SharePoint admin center)

Everything below can be done at `https://fvcn-admin.sharepoint.com` as a SharePoint Administrator or Global Administrator. No PowerShell needed.

### 1. Inspect

1. In a normal tab, open `https://fvcn.sharepoint.com/sites/TVCHub`.
   - **"Site not found" (404)** means the URL is free. Good.
   - **Lands on another site** means a redirect stub is holding the URL. Redirect stubs do not appear in Active sites; see "Clearing a redirect stub" below.
2. Admin center > Sites > **Deleted sites**. Search `TVCHub`. If listed, select it > **Delete permanently**.
3. Admin center > Sites > **Active sites**. Note the URL of the root site (first row, `https://fvcn.sharepoint.com`) and of each campus site. Add the **Hub** column via the column chooser to see which sites are hubs or associated to one.
4. Admin center > **Settings** > **Site creation**. If "Use the form at this URL" is filled in, that is what has been rerouting **+ Create site**. Clear it or leave it; step 2 below bypasses it either way.

### 2. Create

1. Active sites > **+ Create** > **Communication site** > **Standard communication** (Topic).
2. Site name `TVC Hub`. Site address `TVCHub`. Site owner: you.
3. Set **Language** and **Time zone** before Finish. Neither can be changed later.
4. **Finish**. Build content, theme, and navigation. **Do not register it as a hub yet.**

### 3. Swap the root (before launch)

1. Active sites > select the **root site** row (`https://fvcn.sharepoint.com`).
2. If its Hub column says it is a hub: command bar **Hub** > **Unregister as hub site**.
3. Command bar > **Replace site**. Choose `https://fvcn.sharepoint.com/sites/TVCHub` as the new root. Confirm. The admin center assigns the archive URL itself (`/sites/archive-<UTC timestamp>`); note it from Active sites afterwards.
   - The Replace site button is only offered when the tenant has fewer than 10,000 sites, which is us.
   - Both sites are unavailable for several minutes. Never Sunday morning.
4. When the swap finishes, the classic site is at the archive URL. Active sites > select it > if **Lock state** is not Unlocked, set it to Unlocked so staff can still reach old content.
5. `/sites/TVCHub` now redirects to the root. That is fine.

### 4. Finish

1. Active sites > select the root site > **Hub** > **Register as hub site**. Name `TVC Hub`. Leave "who can associate" empty so any site owner can.
2. Settings > **Home site** > set `https://fvcn.sharepoint.com`. This gives the hub the **Home** button in the SharePoint app bar and makes it the Viva Connections landing page in Teams.
3. For each campus site: Active sites > select it > **Hub** > **Associate with a hub** > TVC Hub. Repeat as campuses are added.

### Clearing a redirect stub

The admin center does not list redirect stubs, so this one step needs PowerShell or a support ticket. From Windows PowerShell:

```powershell
Connect-SPOService -Url https://fvcn-admin.sharepoint.com
Remove-SPOSite        -Identity https://fvcn.sharepoint.com/sites/TVCHub
Remove-SPODeletedSite -Identity https://fvcn.sharepoint.com/sites/TVCHub
```

Or open a Microsoft 365 support request from the admin center asking them to remove the redirect site at that URL.

## After launch

- Apply the brand theme to the hub. Associated sites inherit its theme and top navigation.
- Hub navigation should list campuses, not departments, so a third campus is one more link.
- Wait to hand out the URL until the old classic site's owners know traffic is moving. Set a banner or a redirect on the classic site pointing to the hub once content has moved.

## Does this affect VillageOps?

No. VillageOps (repo `fvcnapps/tvc-work-orders`) delivers receipts and reports to the FinanceHR site by site ID, not to the root. The root swap does not touch it.

## Tenant snapshot, 2026-09-10

From the Active sites export the day TVC Hub was created. 39 sites, no hubs anywhere.

- **Root** `https://fvcn.sharepoint.com` is a classic team site from 2014. 0.39 GB, 75 files, still seeing a few page views a week (last activity 9/2/2026). Someone uses it. Before the swap, find out who and what, because every link into it breaks when it moves to the archive URL.
- **TVC Hub** `/sites/TVCHub` created 9/10/2026. Communication site, not a hub, external sharing off. Correct starting state for the swap.
- **Campus sites.** Pottstown has one: `/sites/PottstownCampus` (Teams-connected). Fairview does not; its content is the classic root. Create `/sites/FairviewCampus` as a peer so the hub navigation treats campuses identically. `/sites/TheVillageNorristown` plus the TVN Leadership and TVN Regular Volunteers sites are an **outreach ministry**, not a campus (confirmed 2026-09-10). They sit under Ministries in the hub navigation.
- **Department sites** (all Teams-connected, created April to July 2026): A/V Production, Adult Ministries, Church Board, Communications, Counseling Center, Early Learning Center, Events, Facilities, Finance / HR, Information Technology, Kids Ministry, Leadership Team, Office Admins, Sunday Services (105 GB), The Village Church - Staff, Worship Arts, Young Adults, Youth Ministry. These are the sites worth associating with the hub so they pick up its theme and top navigation.
- **Legacy sites** from 2017 to 2021 with 1 GB quotas and no recent activity: Admin, ALLSTAFF, Fairview Online Files, Infant/Toddler, MINISTRY TEAM, Missions Team, PASTORS, PASTORS and DIRECTORS, Prayer Requests, prayerteam, PROGRAMS, SERMONS. Leave them out of the hub. Review for archival after launch.

### Hub structure

One hub at the root. Top navigation lists campuses first, then ministries, then departments. Every campus, ministry, and department site associates with the hub. A new campus is one new site plus one association and one navigation link.

### Hub navigation, first draft

Mission order guides the grouping: Celebrate (worship and services), Connect (campuses and ministries), Care (outreach and support). Labels are what staff say, not site names.

| Top level | Links | Site |
|-----------|-------|------|
| **Home** | | `https://fvcn.sharepoint.com` |
| **Campuses** | Fairview | `/sites/FairviewCampus` (to create) |
| | Pottstown | `/sites/PottstownCampus` |
| **Ministries** | Kids | `/sites/KidsMinistry` |
| | Youth | `/sites/YouthMinistry` |
| | Young Adults | `/sites/YoungAdultsMin` |
| | Adults | `/sites/AdultMInistries` |
| | Worship Arts | `/sites/WorshipArts2` |
| | Counseling Center | `/sites/CounselingCenter` |
| | Early Learning Center | `/sites/EarlyLearningCenter` |
| | The Village Norristown | `/sites/TheVillageNorristown` |
| | Homeless Ministry | `/sites/homeless.ministry` |
| **Departments** | Communications | `/sites/Communications` |
| | Events | `/sites/ExternalEvents` |
| | Facilities | `/sites/Facilities186` |
| | Finance / HR | `/sites/FinanceHR` |
| | Information Technology | `/sites/InformationTechnology` |
| | Office Admins | `/sites/OfficeAdmins` |
| | A/V Production | `/sites/AV-Production` |
| | Sunday Services | `/sites/SundayServices` |
| **Staff** | Staff Team | `/sites/TheVillageChurch-Staff` |
| | Leadership Team | `/sites/LeadershipTeam` |
| | Church Board | `/sites/ChurchBoard` |
| | VillageOps | work orders app URL |

Notes:

- Staff, Leadership Team, and Church Board are permission-trimmed. Hub navigation shows a link to everyone, but the site denies anyone without access. Use audience targeting on those links so board and leadership items only appear to their members.
- TVN Leadership and TVN Regular Volunteers stay unlinked. They are working sites for that ministry, reachable from The Village Norristown's own navigation.
- Legacy sites (Admin, ALLSTAFF, PASTORS, SERMONS, PROGRAMS, and the rest from 2017 to 2021) are not linked. Review for archival.

## Status log

- **2026-09-10** TVC Hub created at `/sites/TVCHub` from the admin center. Registered as a hub site. Our service principal apps were added as site admins so automation can manage it app-only. Root swap: pending. Home site: pending. Associations: pending until after the swap, since unregistering a hub for the swap drops every association.
- **2026-09-10, later** Hub unregistered, Replace site run from the admin center. `https://fvcn.sharepoint.com` is now TVC Hub. Classic root archived; `/sites/TVCHub` redirects to the root. "Register as hub site" was greyed out for a while after the swap (stale hub record), then worked after a fresh sign-in and a wait. Root is registered as the hub. Pending: home site, archive reachability check, Fairview Campus site, associations, theme and navigation.

- **2026-09-11** Service principal path is live. `TVC SharePoint Admin (automation)` app created with the Azure CLI, certificate uploaded, SharePoint `Sites.FullControl.All` consented (details in `service-principal-admin.md`). Smoke tests passed. Then, all through `spo_admin.py`: TVC tenant theme installed; home site set to the root (`SetSPHSite` wanted `siteUrl`, fixed in the tool); all 21 campus, ministry, department, and staff sites from the navigation list associated with the hub in one loop, no errors. On the hub itself: TVC theme applied, header emphasis Strong, compact layout and mega menu confirmed, white icon set as header logo and color icon as thumbnail, navigation audience targeting enabled. Hub navigation build and Fairview Campus site: in progress the same day. Archive check: the classic root is at `/sites/archive-2026-09-10T171521Z` (title "Fairview Village Church Team Site", template STS#0, lock state Unlock, Active), not at the `ClassicRoot-Archive` URL we asked for; `/sites/ClassicRoot-Archive` is a 404. Runbook corrected. **Fairview Campus created** at `/sites/FairviewCampus` as a peer to Pottstown: private Microsoft 365 group `Fairview Campus` (alias `FairviewCampus`, group id `06bb0cdd-66e5-4006-8be2-dfb10a68e5cf`, owner Micah), site provisioned by SharePoint from the group, associated with the hub. Group-connected creation through the service principal (`GroupSiteManager/CreateGroupEx`) returned 403 because the app has no Graph group permission, so the group was created through Graph with Micah's Azure CLI sign-in and the rest ran as the service principal. No Team was created for it yet; Pottstown has one. Group mail defaulted to `FairviewCampus@fvcn.onmicrosoft.com`; Pottstown's uses `@fvcn.org`. Fix in the Exchange admin center if it matters.

### Lesson

After Replace site, expect the Hub command to be greyed out on the new root for up to an hour. Sign in fresh and wait. Do not create a second hub or re-run the swap.

Once the service principal exists, the admin center is not needed for hubs, associations, home site, or themes. The REST parameter names differ from the PowerShell ones in places (`siteUrl`, not `sphSiteUrl`); `service-principal-admin.md` keeps the verified list.
