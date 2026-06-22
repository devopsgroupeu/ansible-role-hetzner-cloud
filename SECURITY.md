# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

We take the security of this role seriously. If you discover a security vulnerability, please follow these steps.

### Do Not Open a Public Issue

Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.

### Report Privately

Report security vulnerabilities by emailing:

**Email:** security@devopsgroup.sk

Please include:

- Type of vulnerability (e.g. credential exposure, privilege escalation, injection)
- Full paths of source files related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact assessment

### Response Timeline

- Acknowledgement within 3 business days
- Regular updates on progress
- Security patch within 30 days for critical vulnerabilities
- Public disclosure coordinated with the reporter after the fix is released

## Security Best Practices

### Token Management

1. **Never hardcode the API token.** The `hcloud_api_token` variable must be resolved at runtime from HashiCorp Vault, Ansible Vault, or the `HCLOUD_TOKEN` environment variable.

2. **Rotate tokens regularly.** Use project-scoped tokens in Hetzner Cloud with the minimum required permissions.

3. **Use `hcloud_no_log: true` (default).** This suppresses task output that may contain the API token or cloud-init join tokens. Only disable temporarily for debugging.

### Teardown Guard

The `hcloud_allow_teardown: false` default prevents accidental resource deletion. Require explicit `-e hcloud_allow_teardown=true` for destructive runs and scope them with `--tags`.

### Labels and Inventory

The `hcloud_managed_label_*` labels ensure the role only interacts with resources it created. Never modify these labels manually.

### Credential Files

- `.gitignore` excludes `vault.yml`, `*.vault`, `.env`, and `cloud-config-hcloud.ini`
- Never commit credentials in `vars/`, `defaults/`, or `files/`

## Security Updates

Security updates are announced via:

1. GitHub Security Advisories
2. Git tags with security notes
3. `CHANGELOG.md` with a `[SECURITY]` prefix

**Last Updated:** 2026-06-18
