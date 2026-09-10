<#
.SYNOPSIS
  Create the TVC Hub communication site and, when ready, swap it into the tenant root.

.DESCRIPTION
  Run from a machine with the SharePoint Online Management Shell installed.
  Every phase is safe to re-run. Nothing destructive happens without an explicit prompt.

    .\TVCHub.ps1 -Phase Inspect                       # read-only: what is at each URL right now
    .\TVCHub.ps1 -Phase Create                        # clear a stale redirect/deleted stub, create /sites/TVCHub
    .\TVCHub.ps1 -Phase Swap                          # replace the classic root with /sites/TVCHub (prompts)
    .\TVCHub.ps1 -Phase Finish                        # register root as hub + home site, associate campuses

  Do NOT register /sites/TVCHub as a hub before the swap. Invoke-SPOSiteSwap refuses hub sites.

.NOTES
  Requires: Install-Module Microsoft.Online.SharePoint.PowerShell -Scope CurrentUser
  Role:     SharePoint Administrator or Global Administrator
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidateSet('Inspect', 'Create', 'Swap', 'Finish')]
  [string]$Phase,

  [string]$Tenant     = 'fvcn',
  [string]$HubPath    = '/sites/TVCHub',
  [string]$Title      = 'TVC Hub',
  [string]$Owner      = 'micah.roemmich@fvcn.org',

  # Where the old classic root site goes after the swap. Must not exist yet.
  [string]$ArchivePath = '/sites/ClassicRoot-Archive',

  # Campus sites to associate with the hub in the Finish phase. Add campuses here as we grow.
  [string[]]$CampusPaths = @('/sites/Fairview', '/sites/Pottstown')
)

$ErrorActionPreference = 'Stop'
$root    = "https://$Tenant.sharepoint.com"
$admin   = "https://$Tenant-admin.sharepoint.com"
$hubUrl  = "$root$HubPath"
$archive = "$root$ArchivePath"

function Get-SiteOrNull([string]$Url) {
  try { Get-SPOSite -Identity $Url -ErrorAction Stop } catch { $null }
}
function Get-DeletedOrNull([string]$Url) {
  try { Get-SPODeletedSite -Identity $Url -ErrorAction Stop } catch { $null }
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

Import-Module Microsoft.Online.SharePoint.PowerShell -ErrorAction Stop
Write-Host "Connecting to $admin ..."
Connect-SPOService -Url $admin

switch ($Phase) {

  'Inspect' {
    Show-Site 'Root'    $root
    Show-Site 'Hub'     $hubUrl
    Show-Site 'Archive' $archive
    foreach ($p in $CampusPaths) { Show-Site 'Campus' "$root$p" }
    ''
    'Site creation settings (a custom form here is what reroutes "+ Create site"):'
    Get-SPOTenant | Select-Object SelfServiceSiteCreationDisabled, CustomizedSiteCreationForm, `
                                  DefaultLinkPermission, NoAccessRedirectUrl | Format-List
  }

  'Create' {
    $existing = Get-SiteOrNull $hubUrl
    if ($existing -and $existing.Template -eq 'REDIRECTSITE#0') {
      Write-Host "A redirect stub is holding $hubUrl."
      Confirm-Or-Exit 'Remove the redirect stub?'
      Remove-SPOSite -Identity $hubUrl -Confirm:$false
      $existing = $null
    } elseif ($existing) {
      Write-Host "$hubUrl already exists (template $($existing.Template)). Nothing to create."
      break
    }
    if (Get-DeletedOrNull $hubUrl) {
      Write-Host "$hubUrl is in the recycle bin and is holding the URL."
      Confirm-Or-Exit 'Permanently delete it so the URL can be reused?'
      Remove-SPODeletedSite -Identity $hubUrl -Confirm:$false
    }
    Write-Host "Creating communication site $Title at $hubUrl ..."
    New-SPOSite -Url $hubUrl -Title $Title -Owner $Owner -Template 'SITEPAGEPUBLISHING#0' -StorageQuota 1024
    Write-Host 'Created. Build content, theme, and navigation there before running -Phase Swap.'
    Write-Host 'Do not register it as a hub yet.'
  }

  'Swap' {
    $rootSite = Get-SiteOrNull $root
    $hubSite  = Get-SiteOrNull $hubUrl
    if (-not $hubSite) { throw "$hubUrl does not exist. Run -Phase Create first." }
    if ($hubSite.Template -ne 'SITEPAGEPUBLISHING#0') { throw "$hubUrl is not a communication site (template $($hubSite.Template))." }
    if ($hubSite.IsHubSite) { throw "$hubUrl is registered as a hub. Unregister-SPOHubSite it first; the swap refuses hub sites." }
    if ($hubSite.HubSiteId -ne [guid]::Empty) { throw "$hubUrl is associated with a hub. Remove-SPOHubSiteAssociation first." }
    if ($rootSite.IsHubSite) {
      Write-Host "The current root is registered as a hub. It must be unregistered before the swap."
      Confirm-Or-Exit "Unregister $root as a hub?"
      Unregister-SPOHubSite -Identity $root -Confirm:$false
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

    Invoke-SPOSiteSwap -SourceUrl $hubUrl -TargetUrl $root -ArchiveUrl $archive
    Write-Host 'Swap submitted. Polling until the new root reports Active ...'
    do {
      Start-Sleep -Seconds 20
      $s = Get-SiteOrNull $root
      $status = if ($s) { $s.Status } else { 'pending' }
      Write-Host "  root status: $status"
    } while (-not $s -or $s.Status -ne 'Active')

    $arch = Get-SiteOrNull $archive
    if ($arch -and $arch.LockState -ne 'Unlock') {
      Write-Host "Archived classic site is locked ($($arch.LockState)). Unlocking so staff can still reach old content."
      Set-SPOSite -Identity $archive -LockState Unlock
    }
    Write-Host "Done. Old classic root is at $archive. Run -Phase Finish next."
  }

  'Finish' {
    $rootSite = Get-SiteOrNull $root
    if (-not $rootSite.IsHubSite) {
      Write-Host "Registering $root as a hub ..."
      Register-SPOHubSite -Site $root -Principals $null | Out-Null
    }
    Write-Host "Setting $root as the tenant home site (Viva Connections + Home in the app bar) ..."
    Set-SPOHomeSite -HomeSiteUrl $root

    foreach ($p in $CampusPaths) {
      $url = "$root$p"
      if (-not (Get-SiteOrNull $url)) { Write-Warning "Campus site $url not found. Skipping."; continue }
      Write-Host "Associating $url with the hub ..."
      Add-SPOHubSiteAssociation -Site $url -HubSite $root
    }
    Write-Host 'Finished. Apply the brand theme on the hub; associated sites inherit it.'
  }
}
