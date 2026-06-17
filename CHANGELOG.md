# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Phase 5: CI, live molecule scenario, docs, and Galaxy readiness
- `.gitlab-ci.yml` — lint/test/disabled-release stages; `molecule:live` manual/schedule job
- `.github/workflows/ci.yml` — yamllint + ansible-lint + molecule default matrix (debian12/13, ubuntu2204/2404)
- `.github/workflows/galaxy.yml` — SemVer-tag-guarded Galaxy publish (pinned action v1.2.1)
- `molecule/live/` — delegated live scenario (needs `HCLOUD_TOKEN`; NOT part of default CI; always destroys)
- `docs/CONFIGURATION.md` — full variable reference for all `hcloud_*` vars
- `docs/INTEGRATION.md` — dynamic inventory hand-off, rke2 and haproxy-keepalived integration
- `docs/TROUBLESHOOTING.md` — token/auth, rate limits, idempotency, teardown, offline testing
- `README.md` — complete public variable contract, auth/Vault section, dynamic inventory snippet, offline-test note
- Phase 1–4: Galaxy-ready skeleton with offline-safe molecule scenario
- `defaults/main.yml` — all `hcloud_*` variables, every resource list defaults to `[]`
- `meta/main.yml` — Galaxy metadata (namespace: devopsgroupeu, role: hetzner_cloud)
- `meta/argument_specs.yml` — 1:1 with defaults, full type/choice validation
- `tasks/validate.yml` — configuration assertions (no API, runs under `tags: always`)
- `tasks/preflight.yml` — collection availability check (no API)
- `tasks/main.yml` — orchestrator with `module_defaults` group/hetzner.hcloud block
- `tasks/outputs.yml` — stub exposing `hcloud_provisioned_servers` fact
- Resource task files (`ssh_keys.yml`, `networks.yml`, `subnetworks.yml`,
  `firewalls.yml`, `placement_groups.yml`, `servers.yml`, `server_networks.yml`,
  `primary_ips.yml`, `floating_ips.yml`, `volumes.yml`, `load_balancers.yml`)
- `molecule/default/` — offline render/validate scenario (no HCLOUD_TOKEN needed)
- `requirements.yml` — `hetzner.hcloud >=4.0.0`
- `requirements.txt` — pinned test tooling matching sibling roles
- `templates/hcloud_inventory.ini.j2` — static inventory template (Phase 4)
- `examples/rke2_cluster.yml` — full HA RKE2 topology example
- `examples/teardown.yml` — safe teardown walkthrough
- `.ansible-lint` (profile: production), `.yamllint`, `.editorconfig`, `.gitignore`

## [1.0.0] - 2026-06-18

Initial release — functionally complete role ready for Galaxy publish.
