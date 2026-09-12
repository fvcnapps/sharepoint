#!/usr/bin/env python3
"""
spo-admin: SharePoint Online tenant administration as a service principal.

Talks to SharePoint's admin REST with an app-only token. Microsoft Graph has no
API for tenant themes, hub sites, or hub navigation, so this is the path automation
has to take. SharePoint accepts app-only tokens for this REST only when the app
authenticates with a certificate; a client secret is rejected.

Environment:
  SPO_TENANT        short tenant name, default fvcn
  SPO_TENANT_ID     Entra directory (tenant) id
  SPO_CLIENT_ID     app registration client id
  SPO_CERT_PEM      path to a PEM file holding the private key and certificate

Usage:
  spo_admin.py theme list
  spo_admin.py theme add  --name TVC --palette theme/tvc.theme.json
  spo_admin.py theme delete --name TVC
  spo_admin.py theme apply https://fvcn.sharepoint.com --name TVC --palette theme/tvc.theme.json
  spo_admin.py site  get   https://fvcn.sharepoint.com/sites/PottstownCampus
  spo_admin.py site  status --url https://fvcn.sharepoint.com/sites/FairviewCampus
  spo_admin.py site  create --url https://fvcn.sharepoint.com/sites/FairviewCampus --title "Fairview Campus" \
                            --type communication --owner someone@fvcn.org --hub https://fvcn.sharepoint.com --yes
  spo_admin.py hub   list
  spo_admin.py hub   register  https://fvcn.sharepoint.com --title "TVC Hub"
  spo_admin.py hub   set https://fvcn.sharepoint.com --title "TVC Hub" --logo /SiteAssets/fvc-icon-white.png
  spo_admin.py hub   associate https://fvcn.sharepoint.com/sites/PottstownCampus --hub https://fvcn.sharepoint.com
  spo_admin.py hub   disassociate https://fvcn.sharepoint.com/sites/PottstownCampus
  spo_admin.py home-site get
  spo_admin.py home-site set https://fvcn.sharepoint.com
  spo_admin.py web   get https://fvcn.sharepoint.com
  spo_admin.py web   set https://fvcn.sharepoint.com --header-layout compact --header-emphasis strong --mega-menu on
  spo_admin.py logo  get https://fvcn.sharepoint.com
  spo_admin.py logo  set https://fvcn.sharepoint.com --header brand/logo/fvc-icon-white.png --thumbnail brand/logo/fvc-icon-color.png
  spo_admin.py footer get https://fvcn.sharepoint.com
  spo_admin.py footer set https://fvcn.sharepoint.com --title "Celebrate · Connect · Care"
  spo_admin.py nav   get   https://fvcn.sharepoint.com
  spo_admin.py nav   apply https://fvcn.sharepoint.com --spec nav/hub-nav.json [--prune]
  spo_admin.py nav   add   https://fvcn.sharepoint.com --title Fairview --url /sites/FairviewCampus --parent Campuses

Hub navigation is the hub web's own TopNavigationBar; associated sites read it through HubSiteData.
"""
import argparse, json, os, sys
from datetime import datetime, timezone
from functools import lru_cache
from urllib.parse import urlparse

import msal
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

JSON = "application/json;odata=nometadata"
LINKLESS = "http://linkless.header/"  # SharePoint's marker Url for a label-only (mega menu heading) node

# Enum values read back from _api/web and used by Change the look.
HEADER_LAYOUT = {"standard": 1, "compact": 2, "minimal": 3, "extended": 4}
EMPHASIS = {"none": 0, "neutral": 1, "soft": 2, "strong": 3}
FOOTER_LAYOUT = {"simple": 1, "extended": 2}
ONOFF = {"on": True, "off": False}

# Footer state lives in a navigation MenuState keyed by these fixed GUIDs (PnP.Framework Constants.cs).
FOOTER_NODEKEY = "13b7c916-4fea-4bb2-8994-5cf274aeb530"
FOOTER_TITLENODEKEY = "7376cd83-67ac-4753-b156-6a7b3fa0fc1f"
FOOTER_LOGONODEKEY = "2e456c2e-3ded-4a6c-a9ea-f7ac4c1b5100"
FOOTER_MENUNODEKEY = "3a94b35f-030b-468e-80e3-b75ee84ae0ad"
TOPNAV_NODEKEY = "1002"  # the TopNavigationBar collection's node id on every web

# SPSiteManager/create. Site design ids are the built-in communication site designs.
WEB_TEMPLATE = {"communication": "SITEPAGEPUBLISHING#0", "team": "STS#3"}
SITE_DESIGN = {"topic": "96c933ac-3698-44c7-9f4a-5fd17d71af9e", "showcase": "6142d2a0-63a5-4ba0-aede-d9fefca2c767",
               "blank": "f6cc5403-0d63-442e-96c0-285923709ffc"}
SITE_STATUS = {0: "not found", 1: "provisioning", 2: "ready", 3: "error"}


def env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        sys.exit(f"missing environment variable {name}")
    return v


def load_cert(pem_path):
    data = open(pem_path, "rb").read()
    key = serialization.load_pem_private_key(data, password=None)
    cert = x509.load_pem_x509_certificate(data)
    return {
        "private_key": key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
        "thumbprint": cert.fingerprint(hashes.SHA1()).hex(),
        "public_certificate": cert.public_bytes(serialization.Encoding.PEM).decode(),
    }


@lru_cache(maxsize=None)
def app():
    return msal.ConfidentialClientApplication(
        env("SPO_CLIENT_ID"),
        authority=f"https://login.microsoftonline.com/{env('SPO_TENANT_ID')}",
        client_credential=load_cert(env("SPO_CERT_PEM")),
    )


@lru_cache(maxsize=None)
def token_for(host):
    """One token per SharePoint host. The admin host and the content host are different audiences."""
    result = app().acquire_token_for_client(scopes=[f"https://{host}/.default"])
    if "access_token" not in result:
        sys.exit(f"token error for {host}: {result.get('error_description', result)}")
    return result["access_token"]


def call(url, method="GET", body=None, headers=None, raw=None):
    """One REST call. body is JSON-encoded; raw sends bytes as application/octet-stream. headers are merged in."""
    host = urlparse(url).netloc
    h = {"Authorization": f"Bearer {token_for(host)}", "Accept": JSON, "Content-Type": JSON}
    if raw is not None:
        h["Content-Type"] = "application/octet-stream"
    h.update(headers or {})
    r = requests.request(method, url, headers=h, data=raw if raw is not None else (json.dumps(body) if body is not None else None), timeout=60)
    if r.status_code >= 400:
        sys.exit(f"{method} {url}\n{r.status_code} {r.text[:2000]}")
    return r.json() if r.text.strip() else {}


def merge(url, body):
    """OData MERGE: update only the properties in body."""
    return call(url, "POST", body, headers={"X-HTTP-Method": "MERGE", "IF-MATCH": "*"})


def delete(url):
    return call(url, "POST", headers={"X-HTTP-Method": "DELETE", "IF-MATCH": "*"})


def tenant():
    return env("SPO_TENANT", "fvcn")


def admin_url():
    return f"https://{tenant()}-admin.sharepoint.com"


def root_url():
    return f"https://{tenant()}.sharepoint.com"


def name_of(mapping, value):
    return next((k for k, v in mapping.items() if v == value), str(value))


def web_relative(url):
    """Server-relative path of a web, '' for the root so paths join cleanly."""
    return urlparse(url).path.rstrip("/")


# ---- themes -----------------------------------------------------------------

def theme_list(_):
    opts = call(f"{admin_url()}/_api/thememanager/GetTenantThemingOptions", "POST", {})
    for t in opts.get("themePreviews", []):
        print(t.get("name"))
    if not opts.get("themePreviews"):
        print(json.dumps(opts, indent=2))


def theme_json(a):
    palette = json.load(open(a.palette))
    return json.dumps({"isInverted": a.inverted, "name": a.name, "palette": palette})


def theme_add(a):
    body = {"name": a.name, "themeJson": theme_json(a)}
    print(json.dumps(call(f"{admin_url()}/_api/thememanager/AddTenantTheme", "POST", body), indent=2))


def theme_delete(a):
    print(json.dumps(call(f"{admin_url()}/_api/thememanager/DeleteTenantTheme", "POST", {"name": a.name}), indent=2))


def theme_apply(a):
    # Same as Change the look > Theme on the site. Returns the themed catalog path, e.g. /_catalogs/theme/Themed/E1DD246E.
    body = {"name": a.name, "themeJson": theme_json(a)}
    print(json.dumps(call(f"{a.url}/_api/thememanager/ApplyTheme", "POST", body), indent=2))


# ---- sites and hubs ---------------------------------------------------------

def site_get(a):
    props = call(f"{a.url}/_api/site?$select=Id,Url,HubSiteId,IsHubSite")
    web = call(f"{a.url}/_api/web?$select=Title,WebTemplate,Configuration")
    print(json.dumps({**props, **web}, indent=2))


def site_status(a):
    # Read-only. SiteStatus: 0 not found, 1 provisioning, 2 ready, 3 error.
    r = call(f"{root_url()}/_api/SPSiteManager/status?url='{a.url}'")
    r["SiteStatusName"] = SITE_STATUS.get(r.get("SiteStatus"), "unknown")
    print(json.dumps(r, indent=2))


def site_create(a):
    """Modern site without a group (communication or STS#3 team site). Field names per PnP.Framework SiteCollection.cs."""
    req = {
        "Title": a.title, "Url": a.url, "Lcid": a.lcid, "ShareByEmailEnabled": False,
        "Classification": "", "Description": a.description or "",
        "WebTemplate": WEB_TEMPLATE[a.type], "WebTemplateExtensionId": "00000000-0000-0000-0000-000000000000",
        "Owner": a.owner,
    }
    if a.type == "communication":
        # SiteDesignId is documented; WebTemplateExtensionId is what actually applies it (sp-dev-docs issue 4810).
        req["SiteDesignId"] = SITE_DESIGN[a.design]
        req["WebTemplateExtensionId"] = SITE_DESIGN[a.design]
    if a.hub:
        req["HubSiteId"] = call(f"{a.hub}/_api/site?$select=Id")["Id"]
    print(json.dumps({"request": req}, indent=2))
    if not a.yes:
        print("dry run: add --yes to create the site")
        return
    r = call(f"{root_url()}/_api/SPSiteManager/create", "POST", {"request": req})
    r["SiteStatusName"] = SITE_STATUS.get(r.get("SiteStatus"), "unknown")
    print(json.dumps(r, indent=2))


def hub_list(_):
    for h in call(f"{admin_url()}/_api/HubSites").get("value", []):
        print(f"{h.get('Title')!s:30} {h.get('SiteUrl')}  {h.get('ID')}")


def hub_register(a):
    body = {"creationInformation": {"Title": a.title, "Description": a.description or "", "SiteDesignId": "00000000-0000-0000-0000-000000000000"}}
    print(json.dumps(call(f"{a.url}/_api/site/RegisterHubSite", "POST", body), indent=2))


def hub_set(a):
    # HubSiteProperties fields (Title, Description, LogoUrl) as in PnP.PowerShell Set-PnPHubSite; MERGE on the admin host.
    body = {k: v for k, v in (("Title", a.title), ("Description", a.description), ("LogoUrl", a.logo)) if v is not None}
    if not body:
        sys.exit("nothing to set")
    hub_id = call(f"{a.url}/_api/site?$select=Id")["Id"]
    merge(f"{admin_url()}/_api/HubSites/GetById('{hub_id}')", body)
    print(json.dumps(call(f"{admin_url()}/_api/HubSites/GetById('{hub_id}')?$select=Title,Description,LogoUrl"), indent=2))


def hub_associate(a):
    hub_id = call(f"{a.hub}/_api/site?$select=Id")["Id"]
    call(f"{a.url}/_api/site/JoinHubSite('{hub_id}')", "POST", {})
    print(f"associated {a.url} -> {a.hub}")


def hub_disassociate(a):
    call(f"{a.url}/_api/site/JoinHubSite('00000000-0000-0000-0000-000000000000')", "POST", {})
    print(f"disassociated {a.url}")


def home_site_get(_):
    # SPHSite/Details returns null even after a home site is set; SPO.Tenant/GetSPHSiteUrl is the reliable read.
    print(json.dumps(call(f"{admin_url()}/_api/SPO.Tenant/GetSPHSiteUrl"), indent=2))


def home_site_set(a):
    # The parameter is siteUrl. sphSiteUrl (the CSOM name) is rejected: "does not exist in method SetSPHSite".
    # Returns the site id on success.
    print(json.dumps(call(f"{admin_url()}/_api/SPHSite/SetSPHSite", "POST", {"siteUrl": a.url}), indent=2))


# ---- web: header, footer, logo (Change the look) ----------------------------

WEB_FIELDS = "Title,HeaderLayout,HeaderEmphasis,MegaMenuEnabled,NavAudienceTargetingEnabled,FooterEnabled,FooterLayout,FooterEmphasis,HideTitleInHeader,SiteLogoUrl"


def web_get(a):
    w = call(f"{a.url}/_api/web?$select={WEB_FIELDS}")
    names = {"HeaderLayout": HEADER_LAYOUT, "HeaderEmphasis": EMPHASIS, "FooterLayout": FOOTER_LAYOUT, "FooterEmphasis": EMPHASIS}
    for k in WEB_FIELDS.split(","):
        v = w.get(k)
        print(f"{k:28} {v!s:8} {name_of(names[k], v) if k in names else ''}".rstrip())


def web_set(a):
    """Only sends the options given. Same MERGE the Change the look panel performs."""
    body = {}
    if a.header_layout: body["HeaderLayout"] = HEADER_LAYOUT[a.header_layout]
    if a.header_emphasis: body["HeaderEmphasis"] = EMPHASIS[a.header_emphasis]
    if a.mega_menu: body["MegaMenuEnabled"] = ONOFF[a.mega_menu]
    if a.nav_audience_targeting: body["NavAudienceTargetingEnabled"] = ONOFF[a.nav_audience_targeting]
    if a.footer: body["FooterEnabled"] = ONOFF[a.footer]
    if a.footer_layout: body["FooterLayout"] = FOOTER_LAYOUT[a.footer_layout]
    if a.footer_emphasis: body["FooterEmphasis"] = EMPHASIS[a.footer_emphasis]
    if a.hide_title: body["HideTitleInHeader"] = ONOFF[a.hide_title]
    if not body:
        sys.exit("nothing to set")
    merge(f"{a.url}/_api/web", body)
    print(f"merged {json.dumps(body)}")
    web_get(a)


def logo_get(a):
    # Square logo (thumbnail, site cards) is Web.SiteLogoUrl. The rectangular header logo is the
    # web property bag key RectSiteLogoUrl (verified live; PnP.PowerShell Get-PnPWebHeader reads only SiteLogoUrl).
    w = call(f"{a.url}/_api/web?$select=SiteLogoUrl")
    props = call(f"{a.url}/_api/web/AllProperties?$select=RectSiteLogoUrl")
    print(f"header (rectangular, aspect 1):  {props.get('RectSiteLogoUrl')}")
    print(f"thumbnail (square, aspect 0):    {w.get('SiteLogoUrl')}")


def upload_site_asset(url, path):
    name = os.path.basename(path)
    folder = f"{web_relative(url)}/SiteAssets"
    call(f"{url}/_api/web/GetFolderByServerRelativeUrl('{folder}')/Files/add(url='{name}',overwrite=true)", "POST", raw=open(path, "rb").read())
    return f"{folder}/{name}"


def set_site_logo(url, relative, aspect):
    # siteiconmanager/setsitelogo: type SiteLogoType (0 WebLogo, 1 HubLogo, 2 HeaderBackground, 3 GlobalNavLogo),
    # aspect SiteLogoAspect (0 Square, 1 Rectangular). Enums from PnP.Core Branding/Internal/Enums.
    call(f"{url}/_api/siteiconmanager/setsitelogo", "POST", {"relativeLogoUrl": relative, "type": 0, "aspect": aspect})


def logo_set(a):
    """Upload PNGs to SiteAssets and set them as header logo (rectangular) and thumbnail (square)."""
    rel = upload_site_asset(a.url, a.header)
    set_site_logo(a.url, rel, 1)
    print(f"header logo    -> {rel}")
    if a.thumbnail:
        rel = upload_site_asset(a.url, a.thumbnail)
        set_site_logo(a.url, rel, 0)
        print(f"thumbnail logo -> {rel}")
    logo_get(a)


def footer_state(url):
    r = call(f"{url}/_api/navigation/MenuState?menuNodeKey='{FOOTER_NODEKEY}'")
    return None if r.get("odata.null") or "StartingNodeKey" not in r else r


def footer_get(a):
    st = footer_state(a.url)
    if not st or not st.get("Nodes"):
        print("footer title: (not set)")
        return
    for n in st["Nodes"]:
        if n.get("Title") == FOOTER_TITLENODEKEY and n.get("Nodes"):
            print(f"footer title: {n['Nodes'][0].get('Title')}")
        if n.get("Title") == FOOTER_LOGONODEKEY:
            print(f"footer logo:  {n.get('SimpleUrl')}")


def footer_set(a):
    """Footer name from Change the look > Footer. Stored as a MenuState under fixed node keys (PnP.Framework
    NavigationExtensions.SetFooterTitle). A never-touched footer returns odata.null, so bootstrap it first."""
    web_prefix = web_relative(a.url) or "/"
    st = footer_state(a.url)
    if st is None:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S:Z")
        call(f"{a.url}/_api/navigation/SaveMenuState", "POST", {"menuState": {
            "Version": now, "StartingNodeTitle": FOOTER_MENUNODEKEY, "SPSitePrefix": "/", "SPWebPrefix": web_prefix,
            "FriendlyUrlPrefix": "", "SimpleUrl": "", "Nodes": []}})
        st = footer_state(a.url) or {"Nodes": []}
    title_node = {"NodeType": 0, "Title": FOOTER_TITLENODEKEY, "FriendlyUrlSegment": "",
                  "Nodes": [{"NodeType": 0, "Title": a.title, "FriendlyUrlSegment": ""}]}
    existing = next((n for n in st.get("Nodes") or [] if n.get("Title") == FOOTER_TITLENODEKEY), None)
    if existing:
        title_node["Key"] = existing["Key"]  # update in place rather than adding a second title node
    r = call(f"{a.url}/_api/navigation/SaveMenuState", "POST", {"menuState": {
        "StartingNodeTitle": FOOTER_NODEKEY, "SPSitePrefix": "/", "SPWebPrefix": web_prefix,
        "FriendlyUrlPrefix": "", "SimpleUrl": "", "Nodes": [title_node]}})
    print(f"SaveMenuState -> {r}")
    footer_get(a)


# ---- hub navigation ---------------------------------------------------------

def nav_children(url, node_id):
    return call(f"{url}/_api/web/navigation/GetNodeById({node_id})/Children?$expand=Children").get("value", [])


def nav_tree(url):
    """TopNavigationBar as nested dicts, three levels deep (mega menu maximum)."""
    top = call(f"{url}/_api/web/navigation/TopNavigationBar").get("value", [])
    for n in top:
        n["Children"] = nav_children(url, n["Id"])
        for c in n["Children"]:
            c.setdefault("Children", [])
    return top


def menu_state(url):
    return call(f"{url}/_api/navigation/MenuState?menuNodeKey='{TOPNAV_NODEKEY}'")


def menu_nodes(nodes):
    for n in nodes:
        yield n
        yield from menu_nodes(n.get("Nodes") or [])


def new_window_map(url):
    return {n["Key"]: n.get("OpenInNewWindow") for n in menu_nodes(menu_state(url).get("Nodes") or [])}


def print_tree(nodes, new_win, depth=0):
    for n in nodes:
        url = "(heading)" if n.get("Url") == LINKLESS else n.get("Url")
        flags = []
        if n.get("IsExternal"): flags.append("external")
        if new_win.get(str(n["Id"])): flags.append("new window")
        if n.get("AudienceIds"): flags.append("audience " + ",".join(n["AudienceIds"]))
        print(f"{'  ' * depth}[{n['Id']}] {n['Title']} -> {url}" + (f"  ({'; '.join(flags)})" if flags else ""))
        print_tree(n.get("Children") or [], new_win, depth + 1)


def nav_get(a):
    print_tree(nav_tree(a.url), new_window_map(a.url))


def load_spec(path, web_url):
    """Spec -> desired tree. IsExternal is not part of the spec: SharePoint decides it (true for anything it
    cannot resolve inside the hub's site collection, including /sites/... links and label-only headings)."""
    spec = json.load(open(path))
    groups = spec.get("audiences", {})

    def desired(node):
        try:
            aud = sorted(groups[n].lower() for n in node.get("audiences", []))
        except KeyError as e:
            sys.exit(f"spec: unknown audience {e} on {node.get('title')}")
        return {"title": node["title"], "url": node.get("url", LINKLESS), "audiences": aud,
                "new_window": bool(node.get("new_window", False)), "children": [desired(c) for c in node.get("children", [])]}
    return [desired(n) for n in spec["nodes"]]


def menu_node(d):
    """A new MenuState node. The Children collection POST rejects same-tenant links to other site collections
    ("Cannot open '/sites/X': no such file or folder"); SaveMenuState, which the nav editor uses, accepts them."""
    return {"NodeType": 0, "Title": d["title"], "SimpleUrl": d["url"], "FriendlyUrlSegment": "",
            "AudienceIds": d["audiences"], "OpenInNewWindow": True if d["new_window"] else None,
            "Nodes": [menu_node(c) for c in d["children"]]}


def plan_level(desired, existing, path, prune, plan):
    """Return this level's MenuState node list in spec order; record creates, merges, deletes and reorders in plan."""
    by_title = {}
    for n in existing:
        by_title.setdefault(n["Title"], n)
    result = []
    for d in desired:
        label = f"{path}{d['title']}"
        cur = by_title.get(d["title"])
        if cur is None:
            plan["changes"].append(f"+ create  {label} -> {d['url']}" + (f"  audience {d['audiences']}" if d["audiences"] else "") + ("  new window" if d["new_window"] else ""))
            for c in d["children"]:
                plan["changes"].append(f"+ create  {label}/{c['title']} -> {c['url']}" + (f"  audience {c['audiences']}" if c["audiences"] else "") + ("  new window" if c["new_window"] else ""))
            result.append(menu_node(d))
            continue
        diff = {}
        if cur.get("SimpleUrl") != d["url"]: diff["Url"] = d["url"]
        if sorted(g.lower() for g in cur.get("AudienceIds") or []) != d["audiences"]: diff["AudienceIds"] = d["audiences"]
        if diff:
            plan["merges"][cur["Key"]] = diff
            for k, v in diff.items():
                plan["changes"].append(f"~ update  {label} {k}: {cur.get('SimpleUrl' if k == 'Url' else k)!r} -> {v!r}")
        if bool(cur.get("OpenInNewWindow")) != d["new_window"]:
            cur["OpenInNewWindow"] = d["new_window"] or None
            plan["save"] = True
            plan["changes"].append(f"~ update  {label} OpenInNewWindow -> {d['new_window']}")
        if not diff:
            plan["changes"].append(f"= same    {label}")
        cur["Nodes"] = plan_level(d["children"], cur.get("Nodes") or [], label + "/", prune, plan)
        result.append(cur)
    wanted = {d["title"] for d in desired}
    for n in existing:
        if n["Title"] in wanted:
            continue
        if prune:
            plan["deletes"].append((n["Key"], f"{path}{n['Title']}"))
        else:
            result.append(n)
            plan["changes"].append(f"? extra   {path}{n['Title']} [{n['Key']}] (kept; --prune deletes)")
    old_order = [n["Key"] for n in existing if n["Title"] in wanted or not prune]
    new_order = [n["Key"] for n in result if "Key" in n]
    if new_order != old_order:
        plan["save"] = True
        plan["changes"].append(f"~ reorder {path or '(top level)'}")
    if any("Key" not in n for n in result):
        plan["save"] = True
    return result


def nav_apply(a):
    desired = load_spec(a.spec, a.url)
    st = menu_state(a.url)
    plan = {"changes": [], "merges": {}, "deletes": [], "save": False}
    st["Nodes"] = plan_level(desired, st.get("Nodes") or [], "", a.prune, plan)
    if plan["save"]:
        call(f"{a.url}/_api/navigation/SaveMenuState", "POST", {"menuState": st})
    for key, diff in plan["merges"].items():
        merge(f"{a.url}/_api/web/navigation/GetNodeById({key})", diff)
    for key, label in plan["deletes"]:
        delete(f"{a.url}/_api/web/navigation/GetNodeById({key})")
        plan["changes"].append(f"- delete  {label} [{key}]")
    for c in plan["changes"]:
        print(c)
    n = sum(1 for c in plan["changes"] if c[0] in "+~-")
    print(f"\n{n} change(s), {sum(1 for c in plan['changes'] if c[0] == '=')} unchanged")


def nav_add(a):
    st = menu_state(a.url)
    level = st["Nodes"]
    if a.parent:
        parent = next((n for n in st["Nodes"] if n["Title"] == a.parent), None) or sys.exit(f"no top-level node titled {a.parent!r}")
        level = parent.setdefault("Nodes", [])
    if any(n["Title"] == a.title for n in level):
        sys.exit(f"a node titled {a.title!r} already exists at that level; use nav apply to change it")
    d = {"title": a.title, "url": a.url_, "audiences": sorted(g.lower() for g in a.audience or []), "new_window": a.new_window, "children": []}
    level.append(menu_node(d))
    call(f"{a.url}/_api/navigation/SaveMenuState", "POST", {"menuState": st})
    print(f"created {a.title} -> {a.url_}" + (f" under {a.parent}" if a.parent else ""))


# ---- cli --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(prog="spo_admin.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="group", required=True)

    t = sub.add_parser("theme").add_subparsers(dest="cmd", required=True)
    t.add_parser("list").set_defaults(fn=theme_list)
    x = t.add_parser("add"); x.add_argument("--name", required=True); x.add_argument("--palette", required=True)
    x.add_argument("--inverted", action="store_true"); x.set_defaults(fn=theme_add)
    x = t.add_parser("delete"); x.add_argument("--name", required=True); x.set_defaults(fn=theme_delete)
    x = t.add_parser("apply"); x.add_argument("url"); x.add_argument("--name", required=True); x.add_argument("--palette", required=True)
    x.add_argument("--inverted", action="store_true"); x.set_defaults(fn=theme_apply)

    s = sub.add_parser("site").add_subparsers(dest="cmd", required=True)
    x = s.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=site_get)
    x = s.add_parser("status"); x.add_argument("--url", required=True); x.set_defaults(fn=site_status)
    x = s.add_parser("create"); x.add_argument("--url", required=True); x.add_argument("--title", required=True)
    x.add_argument("--type", choices=WEB_TEMPLATE, required=True); x.add_argument("--owner", required=True)
    x.add_argument("--description"); x.add_argument("--lcid", type=int, default=1033); x.add_argument("--hub")
    x.add_argument("--design", choices=SITE_DESIGN, default="topic", help="communication sites only")
    x.add_argument("--yes", action="store_true", help="actually create; without it the request is only printed")
    x.set_defaults(fn=site_create)

    h = sub.add_parser("hub").add_subparsers(dest="cmd", required=True)
    h.add_parser("list").set_defaults(fn=hub_list)
    x = h.add_parser("register"); x.add_argument("url"); x.add_argument("--title", required=True)
    x.add_argument("--description"); x.set_defaults(fn=hub_register)
    x = h.add_parser("set"); x.add_argument("url"); x.add_argument("--title"); x.add_argument("--description")
    x.add_argument("--logo", help="server-relative or absolute url of the hub logo"); x.set_defaults(fn=hub_set)
    x = h.add_parser("associate"); x.add_argument("url"); x.add_argument("--hub", required=True); x.set_defaults(fn=hub_associate)
    x = h.add_parser("disassociate"); x.add_argument("url"); x.set_defaults(fn=hub_disassociate)

    hs = sub.add_parser("home-site").add_subparsers(dest="cmd", required=True)
    hs.add_parser("get").set_defaults(fn=home_site_get)
    x = hs.add_parser("set"); x.add_argument("url"); x.set_defaults(fn=home_site_set)

    w = sub.add_parser("web").add_subparsers(dest="cmd", required=True)
    x = w.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=web_get)
    x = w.add_parser("set"); x.add_argument("url")
    x.add_argument("--header-layout", choices=HEADER_LAYOUT); x.add_argument("--header-emphasis", choices=EMPHASIS)
    x.add_argument("--mega-menu", choices=ONOFF); x.add_argument("--nav-audience-targeting", choices=ONOFF)
    x.add_argument("--footer", choices=ONOFF); x.add_argument("--footer-layout", choices=FOOTER_LAYOUT)
    x.add_argument("--footer-emphasis", choices=EMPHASIS); x.add_argument("--hide-title", choices=ONOFF)
    x.set_defaults(fn=web_set)

    lg = sub.add_parser("logo").add_subparsers(dest="cmd", required=True)
    x = lg.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=logo_get)
    x = lg.add_parser("set"); x.add_argument("url"); x.add_argument("--header", required=True, help="PNG for the header (rectangular)")
    x.add_argument("--thumbnail", help="PNG for the site thumbnail (square)"); x.set_defaults(fn=logo_set)

    f = sub.add_parser("footer").add_subparsers(dest="cmd", required=True)
    x = f.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=footer_get)
    x = f.add_parser("set"); x.add_argument("url"); x.add_argument("--title", required=True); x.set_defaults(fn=footer_set)

    n = sub.add_parser("nav").add_subparsers(dest="cmd", required=True)
    x = n.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=nav_get)
    x = n.add_parser("apply"); x.add_argument("url"); x.add_argument("--spec", required=True)
    x.add_argument("--prune", action="store_true", help="delete nodes not in the spec"); x.set_defaults(fn=nav_apply)
    x = n.add_parser("add"); x.add_argument("url"); x.add_argument("--title", required=True)
    x.add_argument("--url", dest="url_", required=True); x.add_argument("--parent", help="top-level node title")
    x.add_argument("--audience", action="append", help="Entra group id, repeatable")
    x.add_argument("--new-window", action="store_true"); x.set_defaults(fn=nav_add)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
