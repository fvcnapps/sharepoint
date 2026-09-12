# Runbook: TVC Hub theme, header, and navigation

**Goal:** The hub at `https://fvcn.sharepoint.com` looks like The Village Church and every associated site inherits that look and a shared top navigation. A new campus or ministry site becomes one association plus one navigation link.

**Depends on:** `hub-site-tvchub.md` (hub registered at the root). **Assets:** `theme/` and `brand/`.

## 1. Install the tenant theme

Custom themes cannot be created in the admin center UI. Install once, tenant-wide, as the service principal:

```bash
./scripts/spo-admin/spo_admin.py theme add --name TVC --palette theme/tvc.theme.json
```

Setup for that tool is in `service-principal-admin.md`. The browser console and PowerShell alternatives in `theme/README.md` remain as fallbacks.

Verify with `spo_admin.py theme list` (installed 2026-09-11). Optionally hide the Microsoft defaults in admin center > **Settings** > **Themes** so site owners see only ours.

## 2. Apply it on the hub

Default is the tool; each line is idempotent. Done on the hub 2026-09-11.

```bash
./scripts/spo-admin/spo_admin.py theme apply https://fvcn.sharepoint.com --name TVC --palette theme/tvc.theme.json
./scripts/spo-admin/spo_admin.py web set https://fvcn.sharepoint.com --header-layout compact --header-emphasis strong \
    --mega-menu on --nav-audience-targeting on --footer on --footer-layout simple --footer-emphasis neutral
./scripts/spo-admin/spo_admin.py logo set https://fvcn.sharepoint.com --header brand/logo/fvc-icon-white.png --thumbnail brand/logo/fvc-icon-color.png
./scripts/spo-admin/spo_admin.py web get https://fvcn.sharepoint.com
```

The browser equivalent, and the reasoning behind each value: on `https://fvcn.sharepoint.com`, gear > **Change the look**.

| Panel | Setting | Value | Why |
|-------|---------|-------|-----|
| **Theme** | | TVC (under "From your organization") | brand palette |
| **Header** | Layout | Compact | more content above the fold on phones and kiosks |
| | Background | Strong | burgundy header with white text, per brand |
| | Site logo | `brand/logo/` reverse (white) icon-only version | the header is burgundy; standard logo would disappear |
| | Site logo thumbnail | standard color version, square | shows in search results and site cards on light backgrounds |
| | Site title visibility | On | "TVC Hub" beside the icon; the wordmark is in the logo files but too wide for a compact header |
| **Navigation** | Menu style | Mega menu | four groups and about twenty-five links; cascading menus hide most of them |
| | Site navigation visibility | On | |
| | Site navigation audience targeting | On | needed for Staff, Leadership, Board links below |
| **Footer** | Visibility | On, Simple layout | |
| | Footer name | Celebrate · Connect · Care | tagline; set with `spo_admin.py footer set <hub> --title "Celebrate · Connect · Care"` (done 2026-09-11) |
| | Footer background | Neutral | dark grey band, matches print footers |

Associated sites inherit the theme automatically. Site owners on associated sites see the theme locked in Change the look. They keep their own header and logo.

## 3. Build the hub navigation

Hub navigation appears above every associated site's own nav. It is stored as the hub web's top navigation bar, so it is data we can version: `nav/hub-nav.json` holds the tree below, and the tool applies it.

```bash
./scripts/spo-admin/spo_admin.py nav apply https://fvcn.sharepoint.com --spec nav/hub-nav.json   # add --prune to delete links not in the file
./scripts/spo-admin/spo_admin.py nav get   https://fvcn.sharepoint.com
```

Built 2026-09-11: 5 top-level groups, 23 links, audiences on the Staff group and its links, VillageOps opens in a new window. Edit the JSON, re-run, commit. Browser fallback: **Edit** at the right end of the hub nav bar on the hub. Build these top-level labels with the links under them. Mission order guides the grouping: Celebrate (worship and services), Connect (campuses and ministries), Care (outreach and support).

| Top level | Link label | URL | Audience |
|-----------|-----------|-----|----------|
| **Home** | | `/` | everyone |
| **Campuses** | Fairview | `/sites/FairviewCampus` (create first) | everyone |
| | Pottstown | `/sites/PottstownCampus` | everyone |
| **Ministries** | Kids | `/sites/KidsMinistry` | everyone |
| | Youth | `/sites/YouthMinistry` | everyone |
| | Young Adults | `/sites/YoungAdultsMin` | everyone |
| | Adults | `/sites/AdultMInistries` | everyone |
| | Worship Arts | `/sites/WorshipArts2` | everyone |
| | Counseling Center | `/sites/CounselingCenter` | everyone |
| | Early Learning Center | `/sites/EarlyLearningCenter` | everyone |
| | The Village Norristown | `/sites/TheVillageNorristown` | everyone |
| | Homeless Ministry | `/sites/homeless.ministry` | everyone |
| **Departments** | Communications | `/sites/Communications` | everyone |
| | Events | `/sites/ExternalEvents` | everyone |
| | Facilities | `/sites/Facilities186` | everyone |
| | Finance / HR | `/sites/FinanceHR` | everyone |
| | Information Technology | `/sites/InformationTechnology` | everyone |
| | Office Admins | `/sites/OfficeAdmins` | everyone |
| | A/V Production | `/sites/AV-Production` | everyone |
| | Sunday Services | `/sites/SundayServices` | everyone |
| **Staff** | Staff Team | `/sites/TheVillageChurch-Staff` | The Village Church - Staff group |
| | VillageOps | work orders app URL | The Village Church - Staff group |
| | Leadership Team | `/sites/LeadershipTeam` | Leadership Team group |
| | Church Board | `/sites/ChurchBoard` | Church Board group |

The **Staff** heading itself is also targeted to the Staff group so people outside staff do not see an empty heading. Group ids are in the `audiences` block of `nav/hub-nav.json`; they are the Microsoft 365 groups behind the three Teams-connected sites (read from each site's `GroupId`).

How to set audiences in the browser: while editing a link, the **Audiences to target** field accepts Microsoft 365 groups and security groups, up to ten per link. Each Teams-connected site already has a group of the same name; use it. A link with no audience is visible to everyone who can reach the hub. Audience targeting hides the link; it does not grant or remove permission to the site itself.

Not linked on purpose: TVN Leadership and TVN Regular Volunteers (working sites reachable from The Village Norristown's own nav) and every site from 2017 to 2021 (Admin, ALLSTAFF, PASTORS, SERMONS, PROGRAMS, and the rest). Review those for archival after launch.

## 4. Associate the sites

Done for all 21 sites on 2026-09-11. As the service principal, one line per site (the loop is in `service-principal-admin.md`):

```bash
./scripts/spo-admin/spo_admin.py hub associate https://fvcn.sharepoint.com/sites/PottstownCampus --hub https://fvcn.sharepoint.com
```

Browser fallback: admin center > Active sites > select a row > **Hub** > **Associate with a hub** > TVC Hub. Each association takes a minute to apply the theme and show the hub nav.

Also allow site owners to self-associate later: root row > **Hub** > **Edit hub site settings** > leave "People who can associate sites with this hub" empty.

## 5. Check on a phone

Open the hub on a phone. The mega menu collapses into a hamburger; confirm the four groups read cleanly and the header logo is legible on burgundy. Then check one associated site to see the hub nav sitting above its own nav.

## Adding a campus later

Theme, header, and hub bar are inherited; nothing to configure on the new site.

**Group-connected team site (what Pottstown and Fairview are).** SharePoint refuses app-only group creation (`GroupSiteManager/CreateGroupEx` returns 403 because the admin app has no Graph group permission), so the group is created through Graph by a signed-in admin and everything after that runs as the service principal:

```bash
# 1. private Microsoft 365 group; SharePoint provisions /sites/<alias> from it
az rest --method POST --url https://graph.microsoft.com/v1.0/groups --headers Content-Type=application/json --body '{
  "displayName": "New Campus", "description": "New Campus", "mailNickname": "NewCampus",
  "mailEnabled": true, "securityEnabled": false, "groupTypes": ["Unified"], "visibility": "Private",
  "owners@odata.bind":  ["https://graph.microsoft.com/v1.0/users/<owner object id>"],
  "members@odata.bind": ["https://graph.microsoft.com/v1.0/users/<owner object id>"] }'
az rest --method GET --url "https://graph.microsoft.com/v1.0/groups/<group id>/sites/root"   # triggers provisioning; retry until webUrl appears
# 2. associate, 3. one line under Campuses in nav/hub-nav.json, then
./scripts/spo-admin/spo_admin.py hub associate https://fvcn.sharepoint.com/sites/NewCampus --hub https://fvcn.sharepoint.com
./scripts/spo-admin/spo_admin.py nav apply https://fvcn.sharepoint.com --spec nav/hub-nav.json
```

Add a Team on top later from Teams > Create team > From a group, if the campus staff want chat. Groups created this way get a `@fvcn.onmicrosoft.com` address; change it in the Exchange admin center if the group will receive mail. If we want this fully app-only, grant the admin app Graph `Group.Create` (application) and add a `site create --type group` path; not done yet because it widens the app.

**Communication site (public-facing pages, no group).** Fully service principal:

```bash
./scripts/spo-admin/spo_admin.py site create --url https://fvcn.sharepoint.com/sites/NewCampus --title "New Campus" \
    --type communication --owner <upn> --hub https://fvcn.sharepoint.com --yes     # --hub associates at creation
./scripts/spo-admin/spo_admin.py nav apply https://fvcn.sharepoint.com --spec nav/hub-nav.json
```

## Notes

- **Logo color.** The brand guide (August 2018) specifies burgundy PMS 1815C `#7C2529` for the logo and a black B&W variant. A navy version of the icon exists in circulation; it is not in the guide. Use burgundy unless Communications says otherwise.
- **Fonts.** SharePoint cannot load Gotham or Montserrat into its chrome. The theme controls color only; text uses Segoe UI. Brand fonts belong in page images, banners, and documents.
- **Header emphasis and the logo.** Strong (burgundy) background needs the white reverse logo. If Communications prefers the color logo, switch Background to None and accept a white header. Do not put the color logo on burgundy.
