# Runbook: TVC Hub theme, header, and navigation

**Goal:** The hub at `https://fvcn.sharepoint.com` looks like The Village Church and every associated site inherits that look and a shared top navigation. A new campus or ministry site becomes one association plus one navigation link.

**Depends on:** `hub-site-tvchub.md` (hub registered at the root). **Assets:** `theme/` and `brand/`.

## 1. Install the tenant theme

Custom themes cannot be created in the admin center UI. Install once, tenant-wide, with one of the three methods in `theme/README.md`. From a Mac with no PowerShell, use the browser console method in `theme/add-tenant-theme.js`.

Verify: admin center > **Settings** > **Themes** lists **TVC**. Optionally hide the Microsoft defaults there so site owners see only ours.

## 2. Apply it on the hub

On `https://fvcn.sharepoint.com`: gear > **Change the look**.

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
| | Footer name | Celebrate · Connect · Care | tagline |
| | Footer background | Neutral | dark grey band, matches print footers |

Associated sites inherit the theme automatically. Site owners on associated sites see the theme locked in Change the look. They keep their own header and logo.

## 3. Build the hub navigation

Hub navigation appears above every associated site's own nav. Edit it on the hub: **Edit** at the right end of the hub nav bar. Build these top-level labels with the links under them. Mission order guides the grouping: Celebrate (worship and services), Connect (campuses and ministries), Care (outreach and support).

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

How to set audiences: while editing a link, the **Audiences to target** field accepts Microsoft 365 groups and security groups, up to ten per link. Each Teams-connected site already has a group of the same name; use it. A link with no audience is visible to everyone who can reach the hub. Audience targeting hides the link; it does not grant or remove permission to the site itself.

Not linked on purpose: TVN Leadership and TVN Regular Volunteers (working sites reachable from The Village Norristown's own nav) and every site from 2017 to 2021 (Admin, ALLSTAFF, PASTORS, SERMONS, PROGRAMS, and the rest). Review those for archival after launch.

## 4. Associate the sites

Admin center > Active sites > select a row > **Hub** > **Associate with a hub** > TVC Hub. Do every site in the table above. Each association takes a minute to apply the theme and show the hub nav.

Also allow site owners to self-associate later: root row > **Hub** > **Edit hub site settings** > leave "People who can associate sites with this hub" empty.

## 5. Check on a phone

Open the hub on a phone. The mega menu collapses into a hamburger; confirm the four groups read cleanly and the header logo is legible on burgundy. Then check one associated site to see the hub nav sitting above its own nav.

## Adding a campus later

1. Create the site (Communication site for public-facing campus pages, team site if it is mainly a working space).
2. Associate it with TVC Hub.
3. Add one link under **Campuses** in the hub nav.
4. Nothing else. Theme and header are inherited.

## Notes

- **Logo color.** The brand guide (August 2018) specifies burgundy PMS 1815C `#7C2529` for the logo and a black B&W variant. A navy version of the icon exists in circulation; it is not in the guide. Use burgundy unless Communications says otherwise.
- **Fonts.** SharePoint cannot load Gotham or Montserrat into its chrome. The theme controls color only; text uses Segoe UI. Brand fonts belong in page images, banners, and documents.
- **Header emphasis and the logo.** Strong (burgundy) background needs the white reverse logo. If Communications prefers the color logo, switch Background to None and accept a white header. Do not put the color logo on burgundy.
