# TVC SharePoint theme

`tvc.theme.json` is a SharePoint tenant theme palette built from the brand guide (`../brand/FVCN_BrandingReference_092018.pdf`).

| Slot | Value | Source |
|------|-------|--------|
| themePrimary | `#7C2529` | FVC Burgundy, PMS 1815C |
| themeLighterAlt … themeDarker | tints and shades of the primary | Fluent UI shade algorithm |
| neutralLighterAlt | `#f7f5f0` | Off White |
| neutralTertiaryAlt | `#babbb1` | FVC Light Grey, PMS 413C |
| neutralSecondary | `#65665c` | FVC Dark Grey, PMS 417C |
| neutralPrimary | `#1a1a18` | body text, near-black per the "never pure black" rule |
| accent | `#f1a500` | Website Yellow / YITV Gold |

Contrast: white on primary 9.8:1, primary on off-white 9.0:1, body text on off-white 16:1. All pass WCAG AA and AAA.

## Install

Default is the service principal:

```bash
./scripts/spo-admin/spo_admin.py theme add --name TVC --palette theme/tvc.theme.json
```

Fallbacks if that is not set up yet:

- **Browser, no tooling.** Follow the comments at the top of `add-tenant-theme.js`.
- **Windows PowerShell.**
  ```powershell
  Connect-SPOService -Url https://fvcn-admin.sharepoint.com
  $p = Get-Content .\tvc.theme.json | ConvertFrom-Json -AsHashtable
  Add-SPOTheme -Identity "TVC" -Palette $p -IsInverted $false
  ```
- **PnP.PowerShell (macOS).**
  ```powershell
  Connect-PnPOnline -Url https://fvcn-admin.sharepoint.com -Interactive -ClientId $env:PNP_CLIENT_ID
  Add-PnPTenantTheme -Identity "TVC" -Palette (Get-Content .\tvc.theme.json -Raw) -IsInverted:$false
  ```

Optional: in the admin center, Settings > Themes, hide the Microsoft default themes so site owners only see TVC.

## Preview before installing

Open https://aka.ms/themedesigner, set Primary `#7C2529`, Text `#1a1a18`, Background `#ffffff`. The preview matches this palette closely; the neutrals here are warmed slightly toward the brand greys.
