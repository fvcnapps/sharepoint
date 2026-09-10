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
  spo_admin.py site  get   https://fvcn.sharepoint.com/sites/PottstownCampus
  spo_admin.py hub   list
  spo_admin.py hub   register  https://fvcn.sharepoint.com --title "TVC Hub"
  spo_admin.py hub   associate https://fvcn.sharepoint.com/sites/PottstownCampus --hub https://fvcn.sharepoint.com
  spo_admin.py hub   disassociate https://fvcn.sharepoint.com/sites/PottstownCampus
  spo_admin.py home-site set https://fvcn.sharepoint.com
"""
import argparse, json, os, sys
from functools import lru_cache
from urllib.parse import urlparse

import msal
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

JSON = "application/json;odata=nometadata"


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


def call(url, method="GET", body=None):
    host = urlparse(url).netloc
    r = requests.request(
        method, url,
        headers={"Authorization": f"Bearer {token_for(host)}", "Accept": JSON, "Content-Type": JSON},
        data=json.dumps(body) if body is not None else None, timeout=60,
    )
    if r.status_code >= 400:
        sys.exit(f"{method} {url}\n{r.status_code} {r.text[:2000]}")
    return r.json() if r.text.strip() else {}


def tenant():
    return env("SPO_TENANT", "fvcn")


def admin_url():
    return f"https://{tenant()}-admin.sharepoint.com"


# ---- themes -----------------------------------------------------------------

def theme_list(_):
    opts = call(f"{admin_url()}/_api/thememanager/GetTenantThemingOptions", "POST", {})
    for t in opts.get("themePreviews", []):
        print(t.get("name"))
    if not opts.get("themePreviews"):
        print(json.dumps(opts, indent=2))


def theme_add(a):
    palette = json.load(open(a.palette))
    body = {"name": a.name, "themeJson": json.dumps({"isInverted": a.inverted, "name": a.name, "palette": palette})}
    print(json.dumps(call(f"{admin_url()}/_api/thememanager/AddTenantTheme", "POST", body), indent=2))


def theme_delete(a):
    print(json.dumps(call(f"{admin_url()}/_api/thememanager/DeleteTenantTheme", "POST", {"name": a.name}), indent=2))


# ---- sites and hubs ---------------------------------------------------------

def site_get(a):
    props = call(f"{a.url}/_api/site?$select=Id,Url,HubSiteId,IsHubSite")
    web = call(f"{a.url}/_api/web?$select=Title,WebTemplate,Configuration")
    print(json.dumps({**props, **web}, indent=2))


def hub_list(_):
    for h in call(f"{admin_url()}/_api/HubSites").get("value", []):
        print(f"{h.get('Title')!s:30} {h.get('SiteUrl')}  {h.get('ID')}")


def hub_register(a):
    body = {"creationInformation": {"Title": a.title, "Description": a.description or "", "SiteDesignId": "00000000-0000-0000-0000-000000000000"}}
    print(json.dumps(call(f"{a.url}/_api/site/RegisterHubSite", "POST", body), indent=2))


def hub_associate(a):
    hub_id = call(f"{a.hub}/_api/site?$select=Id")["Id"]
    call(f"{a.url}/_api/site/JoinHubSite('{hub_id}')", "POST", {})
    print(f"associated {a.url} -> {a.hub}")


def hub_disassociate(a):
    call(f"{a.url}/_api/site/JoinHubSite('00000000-0000-0000-0000-000000000000')", "POST", {})
    print(f"disassociated {a.url}")


def home_site_set(a):
    print(json.dumps(call(f"{admin_url()}/_api/SPHSite/SetSPHSite", "POST", {"sphSiteUrl": a.url}), indent=2))


# ---- cli --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(prog="spo_admin.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="group", required=True)

    t = sub.add_parser("theme").add_subparsers(dest="cmd", required=True)
    t.add_parser("list").set_defaults(fn=theme_list)
    x = t.add_parser("add"); x.add_argument("--name", required=True); x.add_argument("--palette", required=True)
    x.add_argument("--inverted", action="store_true"); x.set_defaults(fn=theme_add)
    x = t.add_parser("delete"); x.add_argument("--name", required=True); x.set_defaults(fn=theme_delete)

    s = sub.add_parser("site").add_subparsers(dest="cmd", required=True)
    x = s.add_parser("get"); x.add_argument("url"); x.set_defaults(fn=site_get)

    h = sub.add_parser("hub").add_subparsers(dest="cmd", required=True)
    h.add_parser("list").set_defaults(fn=hub_list)
    x = h.add_parser("register"); x.add_argument("url"); x.add_argument("--title", required=True)
    x.add_argument("--description"); x.set_defaults(fn=hub_register)
    x = h.add_parser("associate"); x.add_argument("url"); x.add_argument("--hub", required=True); x.set_defaults(fn=hub_associate)
    x = h.add_parser("disassociate"); x.add_argument("url"); x.set_defaults(fn=hub_disassociate)

    hs = sub.add_parser("home-site").add_subparsers(dest="cmd", required=True)
    x = hs.add_parser("set"); x.add_argument("url"); x.set_defaults(fn=home_site_set)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
