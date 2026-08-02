# Oh My Posh Baseline Design

## Purpose

Add a lightweight, optional Oh My Posh prompt to the user's interactive
PowerShell session. This is a workstation presentation enhancement, not part
of the GoodQ runtime.

## Scope

- Add one guarded initialization block to the current-user PowerShell host
  profile.
- Initialize Oh My Posh only when its executable resolves on `PATH`.
- Use the installed default configuration for the baseline.
- Preserve normal PowerShell behavior when Oh My Posh is unavailable or its
  initialization fails.

## Explicit exclusions

- No changes to `dev_on.bat`, `dev_off.bat`, GoodQ runtime services, WSL,
  startup tasks, or repository configuration.
- No custom theme file, package installation, upgrade, or global environment
  change.
- No dependency on Oh My Posh for automation or non-interactive shells.

## Behavior

At interactive PowerShell startup, the profile checks for `oh-my-posh`. When
present, it evaluates `oh-my-posh init pwsh`; when absent or initialization
fails, it emits no error and leaves the normal prompt intact. The baseline is
validated in a fresh interactive PowerShell session.

## Rollback

Remove only the guarded block from the current-user PowerShell host profile.
No service or repository rollback is required.

## Verification

1. Start a fresh PowerShell session and verify the prompt renders.
2. Run a non-interactive PowerShell command and verify it remains unaffected.
3. Confirm GoodQ Dev On/Off scripts and runtime state are unchanged.
