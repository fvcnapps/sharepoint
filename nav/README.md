# Hub navigation spec

`hub-nav.json` is the source of truth for the TVC Hub navigation (the hub web's TopNavigationBar, which every associated site shows). Apply it with:

```bash
scripts/spo-admin/spo_admin.py nav apply https://fvcn.sharepoint.com --spec nav/hub-nav.json          # create/update
scripts/spo-admin/spo_admin.py nav apply https://fvcn.sharepoint.com --spec nav/hub-nav.json --prune  # also delete nodes not in the spec
scripts/spo-admin/spo_admin.py nav get   https://fvcn.sharepoint.com
```

Idempotent: nodes match by title at each level; only differing Url, IsExternal, or AudienceIds are sent. Order is not rearranged, so new nodes append at the end of their level.

## Shape

- `audiences`: name -> Entra group id. Nodes reference the names, never the GUIDs.
- `nodes[]`: `title`, optional `url` (omit for a label-only mega menu heading), `new_window`, `audiences` (list of names, max 10), `children[]`.
- Site URLs are server-relative (`/sites/Name`), exactly as SharePoint stores them. There is no external flag: SharePoint sets `IsExternal` itself (true for every link outside the hub's own site collection, headings included).
- Nodes are written through `_api/navigation/SaveMenuState`, the call the nav editor uses; the plain `Children` POST rejects links to other site collections.

Adding a campus: one child under **Campuses**, then `nav apply`.
