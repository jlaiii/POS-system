|-
|### Priority: MEDIUM
|
- [~] worker-2 **Enable 2FA for Owner (1111) to comply with mandatory 2FA policy** — `require_2fa_for_admins=true` in security_config.json, but the Owner account (1111) does not have 2FA enabled. This means the mandatory 2FA banner is shown and admin features are blocked for the primary account. Owner needs to set up 2FA via the setup flow or the exemption list needs to be configured. Until resolved, the Owner experiences degraded admin access. [System Auditor #25]
