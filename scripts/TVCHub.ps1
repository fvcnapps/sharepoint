#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Create the TVC Hub communication site and, when ready, swap it into the tenant root.

.DESCRIPTION
  Cross-platform (macOS, Windows, Linux) on PowerShell 7.4+ using PnP.PowerShell.
  Every phase is safe to re-run. Nothing destructive happens without typing YES.

  One-time setup (registers an Entra app PnP signs in through; needs Global Admin consent):
    ./scripts/TVCHub.ps1 -Phase Setup
  Save the Client ID it prints, then pass it to every later run (or set $env:PNP_CLIENT_ID).

    ./scripts/TVCHub.ps1 -Phase Inspect -ClientId <guid>   # read-only: what is at each URL right now
    ./scripts/TVCHub.ps1 -Phase Create  -ClientId <guid>   # clear a stale stub, create /sites/TVCHub
    ./scripts/TVCHub.ps1 -Phase Swap    -ClientId <guid>   # replace the classic root with /sites/TVCHub (prompts)
    ./scripts/TVCHub.ps1 -Phase Finish  -ClientId <guid>   # register root as hub + home site, associate campuses

  Do NOT register /sites/TVCHub as a hub before the swap. The swap refuses hub sites.

.NOTES
  Requires: Install-Module PnP.PowerShell -Scope CurrentUser
  Role:     SharePoint Administrator or Global Administrator
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidateSet('Setup', 'Inspect', 'Create', 'Swap', 'Finish')]
  [string]$Phase,

  # Entra app registration PnP uses to sign in. Created by -Phase Setup.
  [string]$ClientId = $env:PNP_CLIENT_ID,

  [string]$Tenant       = 'fvcn',
  [string]$TenantDomain = 'fvcn.onmicrosoft.com',
  [string]$HubPath      = '/sites/TVCHub',
  [string]$Title        = 'TVC Hub',
  [string]$Owner        = 'micah.roemmich@fvcn.org',

  # Where the old classic root site goes after the swap. Must not exist yet.
  [string]$ArchivePath = '/sites/ClassicRoot-Archive',

  # Sites to associate with the hub in the Finish phase. Campuses first, then shared department sites.
  # Fairview has no campus site yet (its content lives on the classic root); add it once created.
  [string[]]$CampusPaths = @('/sites/PottstownCampus')
)

$ErrorActionPreference = 'Stop'
$root    = "https://$Tenant.sharepoint.com"
$admin   = "https://$Tenant-admin.sharepoint.com"
$hubUrl  = "$root$HubPath"
$archive = "$root$ArchivePath"

Import-Module PnP.PowerShell -ErrorAction Stop

if ($Phase -eq 'Setup') {
  Write-Host 'Registering an Entra app named "PnP PowerShell - TVC SharePoint Admin".'
  Write-Host 'A browser window will open twice: once to sign in, once for admin consent.'
  $app = Register-PnPEntraIDAppForInteractiveLogin -ApplicationName 'PnP PowerShell - TVC SharePoint Admin' `
                                                   -Tenant $TenantDomain -Interactive
  $app | Format-List
  Write-Host ''
  Write-Host 'Save the AzureAppId/ClientId above. Use it as -ClientId, or run:'
  Write-Host '  $env:PNP_CLIENT_ID = "<that guid>"'
  return
}

if (-not $ClientId) { throw 'No -ClientId. Run -Phase Setup once, then pass the Client ID it prints.' }

function Get-SiteOrNull([string]$Url) {
  try { Get-PnPTenantSite -Identity $Url -ErrorAction Stop } catch { $null }
}
function Get-DeletedOrNull([string]$Url) {
  try { Get-PnPTenantDeletedSite -Identity $Url -ErrorAction Stop } catch { $null }
}
function Show-Site([string]$Label, [string]$Url) {
  $s = Get-SiteOrNull $Url
  $d = Get-DeletedOrNull $Url
  if ($s) {
    "{0,-14} {1}`n{2,-14} template={3} status={4} lock={5} hub={6} assocHub={7}" -f `
      $Label, $Url, '', $s.Template, $s.Status, $s.LockState, $s.IsHubSite, $s.HubSiteId
  } elseif ($d) {
    "{0,-14} {1}`n{2,-14} IN RECYCLE BIN (deleted {3}, {4} days left)" -f $Label, $Url, '', $d.DeletionTime, $d.DaysRemaining
  } else {
    "{0,-14} {1}`n{2,-14} not found (URL is free)" -f $Label, $Url, ''
  }
}
function Confirm-Or-Exit([string]$Prompt) {
  $answer = Read-Host "$Prompt  Type YES to continue"
  if ($answer -ne 'YES') { Write-Host 'Stopped. Nothing changed.'; exit 1 }
}

Write-Host "Connecting to $admin ..."
Connect-PnPOnline -Url $admin -Interactive -ClientId $ClientId

switch ($Phase) {

  'Inspect' {
    Show-Site 'Root'    $root
    Show-Site 'Hub'     $hubUrl
    Show-Site 'Archive' $archive
    foreach ($p in $CampusPaths) { Show-Site 'Campus' "$root$p" }
    ''
    'Tenant settings that affect site creation and redirects:'
    $t = Get-PnPTenant
    $t.PSObject.Properties |
      Where-Object { $_.Name -match 'SiteCreation|SelfService|Redirect|HomeSite' } |
      Format-Table Name, Value -AutoSize
    ''
    'Existing hub sites:'
    Get-PnPHubSite | Format-Table Title, SiteUrl -AutoSize
  }

  'Create' {
    $existing = Get-SiteOrNull $hubUrl
    if ($existing -and $existing.Template -eq 'REDIRECTSITE#0') {
      Write-Host "A redirect stub is holding $hubUrl."
      Confirm-Or-Exit 'Remove the redirect stub?'
      Remove-PnPTenantSite -Url $hubUrl -Force -SkipRecycleBin
      $existing = $null
    } elseif ($existing) {
      Write-Host "$hubUrl already exists (template $($existing.Template)). Nothing to create."
      break
    }
    if (Get-DeletedOrNull $hubUrl) {
      Write-Host "$hubUrl is in the recycle bin and is holding the URL."
      Confirm-Or-Exit 'Permanently delete it so the URL can be reused?'
      Remove-PnPTenantDeletedSite -Identity $hubUrl -Force
    }
    Write-Host "Creating communication site $Title at $hubUrl ..."
    New-PnPSite -Type CommunicationSite -Title $Title -Url $hubUrl -Owner $Owner -SiteDesign Topic | Out-Null
    Write-Host 'Created. Build content, theme, and navigation there before running -Phase Swap.'
    Write-Host 'Do not register it as a hub yet.'
  }

  'Swap' {
    $rootSite = Get-SiteOrNull $root
    $hubSite  = Get-SiteOrNull $hubUrl
    if (-not $hubSite) { throw "$hubUrl does not exist. Run -Phase Create first." }
    if ($hubSite.Template -ne 'SITEPAGEPUBLISHING#0') { throw "$hubUrl is not a communication site (template $($hubSite.Template))." }
    if ($hubSite.IsHubSite) { throw "$hubUrl is registered as a hub. Unregister-PnPHubSite it first; the swap refuses hub sites." }
    if ($hubSite.HubSiteId -and $hubSite.HubSiteId -ne [guid]::Empty) { throw "$hubUrl is associated with a hub. Remove-PnPHubSiteAssociation first." }
    if ($rootSite.IsHubSite) {
      Write-Host 'The current root is registered as a hub. It must be unregistered before the swap.'
      Confirm-Or-Exit "Unregister $root as a hub?"
      Unregister-PnPHubSite -Site $root
    }
    if ((Get-SiteOrNull $archive) -or (Get-DeletedOrNull $archive)) {
      throw "$archive already exists (active or deleted). Pick another -ArchivePath."
    }

    Write-Host ''
    Write-Host 'This will:'
    Write-Host "  move  $hubUrl  ->  $root          (becomes the new root)"
    Write-Host "  move  $root  ->  $archive   (old classic root, kept)"
    Write-Host "  leave a redirect at $hubUrl pointing to $root"
    Write-Host 'Both sites are unavailable for several minutes during the swap. Do not run this on a Sunday morning.'
    Confirm-Or-Exit 'Swap the root site now?'

    Invoke-PnPSiteSwap -SourceUrl $hubUrl -TargetUrl $root -ArchiveUrl $archive -Wait -Force
    Write-Host 'Swap complete.'

    $arch = Get-SiteOrNull $archive
    if ($arch -and $arch.LockState -ne 'Unlock') {
      Write-Host "Archived classic site is locked ($($arch.LockState)). Unlocking so staff can still reach old content."
      Set-PnPTenantSite -Identity $archive -LockState Unlock
    }
    Write-Host "Done. Old classic root is at $archive. Run -Phase Finish next."
  }

  'Finish' {
    $rootSite = Get-SiteOrNull $root
    if (-not $rootSite.IsHubSite) {
      Write-Host "Registering $root as a hub ..."
      Register-PnPHubSite -Site $root | Out-Null
    }
    Write-Host "Setting $root as the tenant home site (Viva Connections + Home in the app bar) ..."
    Set-PnPHomeSite -HomeSiteUrl $root

    foreach ($p in $CampusPaths) {
      $url = "$root$p"
      if (-not (Get-SiteOrNull $url)) { Write-Warning "Campus site $url not found. Skipping."; continue }
      Write-Host "Associating $url with the hub ..."
      Add-PnPHubSiteAssociation -Site $url -HubSite $root
    }
    Write-Host 'Finished. Apply the brand theme on the hub; associated sites inherit it.'
  }
}
