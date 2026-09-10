// Installs the TVC theme as a tenant theme without PowerShell.
//
// 1. Sign in to https://fvcn-admin.sharepoint.com as a SharePoint or Global Administrator.
// 2. Stay on that tab. Open the browser developer console (Cmd+Option+J in Chrome or Edge on a Mac).
// 3. Paste this whole file and press Enter. Expect "201" or "200" and a JSON body.
// 4. Reload the admin center. Settings > Themes should now list "TVC". Every site's
//    "Change the look" gets it under "From your organization".
//
// The palette below must match theme/tvc.theme.json. Re-run with a new name to add a revision;
// to replace in place, run the DeleteTenantTheme line at the bottom first.

(async () => {
  const admin = 'https://fvcn-admin.sharepoint.com';
  const name = 'TVC';
  const palette = {
    "themePrimary": "#7C2529",
    "themeLighterAlt": "#faf3f3",
    "themeLighter": "#ead0d1",
    "themeLight": "#d8aaac",
    "themeTertiary": "#b0666a",
    "themeSecondary": "#8c3539",
    "themeDarkAlt": "#702125",
    "themeDark": "#5e1c1f",
    "themeDarker": "#451517",
    "neutralLighterAlt": "#f7f5f0",
    "neutralLighter": "#f1efe9",
    "neutralLight": "#e9e8e2",
    "neutralQuaternaryAlt": "#dcddd6",
    "neutralQuaternary": "#cbccc4",
    "neutralTertiaryAlt": "#babbb1",
    "neutralTertiary": "#8e8f85",
    "neutralSecondary": "#65665c",
    "neutralPrimaryAlt": "#2f2f2c",
    "neutralPrimary": "#1a1a18",
    "neutralDark": "#141412",
    "black": "#0e0e0d",
    "white": "#ffffff",
    "accent": "#f1a500"
  };

  if (location.origin !== admin) {
    console.error(`Run this from a tab on ${admin}, not ${location.origin}`);
    return;
  }
  const json = 'application/json;odata=nometadata';
  const digest = (await (await fetch(`${admin}/_api/contextinfo`, {
    method: 'POST', credentials: 'include', headers: { Accept: json }
  })).json()).FormDigestValue;

  const res = await fetch(`${admin}/_api/thememanager/AddTenantTheme`, {
    method: 'POST', credentials: 'include',
    headers: { Accept: json, 'Content-Type': json, 'X-RequestDigest': digest },
    body: JSON.stringify({
      name,
      themeJson: JSON.stringify({ isInverted: false, name, palette })
    })
  });
  console.log(res.status, await res.text());

  // To remove a theme (for example before re-adding a changed palette):
  // await fetch(`${admin}/_api/thememanager/DeleteTenantTheme`, { method:'POST', credentials:'include',
  //   headers:{ Accept: json, 'Content-Type': json, 'X-RequestDigest': digest }, body: JSON.stringify({ name }) });
})();
