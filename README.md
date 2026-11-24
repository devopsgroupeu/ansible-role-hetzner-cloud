# Ansible Role - Hetzner Cloud

[![CI](https://github.com/devopsgroupeu/ansible-role-hetzner-cloud/actions/workflows/ci.yml/badge.svg)](https://github.com/devopsgroupeu/ansible-role-hetzner-cloud/actions/workflows/ci.yml)
[![Ansible Galaxy](https://img.shields.io/badge/Ansible%20Galaxy-devopsgroupeu.hetzner--cloud-blue?logo=ansible)](https://galaxy.ansible.com/ui/standalone/roles/devopsgroupeu/hetzner-cloud/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![GitHub Forks](https://img.shields.io/github/forks/devopsgroupeu/ansible-role-hetzner-cloud)
![GitHub Stars](https://img.shields.io/github/stars/devopsgroupeu/ansible-role-hetzner-cloud)
![GitHub Issues](https://img.shields.io/github/issues/devopsgroupeu/ansible-role-hetzner-cloud)

[![LinkedIn](https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/devopsgroup8/)
![Hetzner](https://img.shields.io/badge/Hetzner-D50C2D?logo=hetzner&logoColor=fff&style=for-the-badge)

Controller-side Ansible role that provisions Hetzner Cloud infrastructure (SSH keys, networks, subnetworks, firewalls, placement groups, servers, server-network attachments, primary IPs, floating IPs, volumes, and load balancers) via the [`hetzner.hcloud`](https://galaxy.ansible.com/hetzner/hcloud) collection.

**Default posture: does nothing.** Every resource list defaults to `[]`. The role is a no-op until you populate the lists.

---

## Controller-side execution

This role runs on the **Ansible control node** (your workstation or CI runner), not on the target hosts. Always use:

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  become: false
```

This is different from configuration roles, which run on the provisioned hosts.

---

## Installation

Pull this role into your playbook project via a `requirements.yml` git source:

```yaml
roles:
  - name: devopsgroupeu.hetzner-cloud
    src: https://github.com/devopsgroupeu/ansible-role-hetzner-cloud
    scm: git
    version: "v1.1.0"   # use the latest tag
```

```bash
ansible-galaxy install -r requirements.yml
```

Once published to Ansible Galaxy, the role can also be installed by name:

```bash
ansible-galaxy role install devopsgroupeu.hetzner-cloud
```

---

## Requirements

### Collection

Install the `hetzner.hcloud` collection before running the role:

```bash
ansible-galaxy collection install -r requirements.yml
```

`requirements.yml`:

```yaml
collections:
  - name: hetzner.hcloud
    version: ">=6.9.0,<8.0.0"
```

The role supports `hetzner.hcloud` `>=6.9.0,<8.0.0` (checked by `preflight.yml`); CI tests the latest 7.x release. A new major version is only allowed after it has been tested.

### Python

```bash
pip install -r requirements.txt
```

Supported: ansible-core 2.19 to 2.22 (CI runs 2.21 and 2.22). `hetzner.hcloud` 7.x needs Python 3.11+ on the controller (ansible-core 2.22 needs Python 3.13+). The collection vendors the `hcloud` Python SDK; it only needs `python-dateutil` and `requests`, which `requirements.txt` lists.

---

## Authentication

Never hardcode the API token in a vars file or role. Use one of:

1. **Environment variable (CI / workstation):**
   ```bash
   export HCLOUD_TOKEN="your-api-token"
   ```

2. **HashiCorp Vault (recommended for production):**
   ```yaml
   hcloud_api_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'hetzner/token').secret.value }}"
   ```

3. **Ansible Vault:**
   ```yaml
   hcloud_api_token: "{{ vault_hcloud_token }}"
   ```

The `hcloud_api_token` variable defaults to `lookup('ansible.builtin.env', 'HCLOUD_TOKEN')`. If it resolves to an empty string and `hcloud_provision: true`, the role aborts at `validate.yml` with a clear error. Token values are protected by `no_log: true`.

---

## Variable contract

All tunables are prefixed `hcloud_*`. Full documented defaults are in [`defaults/main.yml`](defaults/main.yml). Per-item sub-keys are documented in [`meta/argument_specs.yml`](meta/argument_specs.yml) and [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

### Top-level variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `hcloud_api_token` | str | `$HCLOUD_TOKEN` | API token — source from Vault/env, never hardcode |
| `hcloud_provision` | bool | `true` | Master gate — set `false` for offline/validate-only runs (no token needed) |
| `hcloud_state` | str | `present` | Global default state (`present`\|`absent`) |
| `hcloud_allow_teardown` | bool | `false` | Hard guard — must be `true` to allow any `state: absent` |
| `hcloud_no_log` | bool | `true` | Suppress sensitive output; set `false` for debugging only |
| `hcloud_default_location` | str | `fsn1` | Fallback location slug for servers/IPs |
| `hcloud_default_image` | str | `debian-12` | Fallback OS image for servers |
| `hcloud_managed_label_key` | str | `managed-by` | Label key stamped on every created resource |
| `hcloud_managed_label_value` | str | `ansible-hetzner-cloud` | Label value paired with the managed-by key |
| `hcloud_write_inventory` | bool | `false` | Write a static YAML inventory to `hcloud_inventory_path` |
| `hcloud_inventory_path` | str | `""` | Destination for the static inventory (required if `hcloud_write_inventory: true`) |
| `hcloud_inventory_groups` | dict | `{server_nodes: control-plane, agent_nodes: worker, proxy_hosts: proxy, vault: vault}` | Static inventory groups as group name -> `role` label value; unmatched servers go to `ungrouped` |

### Resource lists (all default to `[]`)

| Variable | Type | Default | Description |
|---|---|---|---|
| `hcloud_ssh_keys` | list[dict] | `[]` | SSH keys to upload. Required sub-keys: `name`. |
| `hcloud_networks` | list[dict] | `[]` | Private networks. Required sub-keys: `name`, `ip_range`. |
| `hcloud_subnetworks` | list[dict] | `[]` | Subnets within networks. Required sub-keys: `network`, `type`, `network_zone`, `ip_range`. |
| `hcloud_firewalls` | list[dict] | `[]` | Firewall rules and `apply_to` bindings (servers or label selectors). Required sub-keys: `name`. |
| `hcloud_placement_groups` | list[dict] | `[]` | Anti-affinity groups. Required sub-keys: `name`, `type` (`spread`). |
| `hcloud_servers` | list[dict] | `[]` | Compute instances. Required sub-keys: `name`, `server_type` (when `state: present`). |
| `hcloud_server_networks` | list[dict] | `[]` | Server-network attachments. Required sub-keys: `server`, `network`. |
| `hcloud_primary_ips` | list[dict] | `[]` | Stable pre-created public IPs. Required sub-keys: `name`, `type`. |
| `hcloud_floating_ips` | list[dict] | `[]` | Floating IPs (e.g. HA VIP for a load balancer). Required sub-keys: `name`, `type`. |
| `hcloud_volumes` | list[dict] | `[]` | Block storage volumes. Required sub-keys: `name`, `size`. |
| `hcloud_load_balancers` | list[dict] | `[]` | Managed load balancers (off by default). Required sub-keys: `name`, `load_balancer_type`. |

Full per-item sub-key documentation is in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

Out of scope (use the `hetzner.hcloud` modules directly): reverse DNS (`rdns`), network routes (`route`), volume detach (`volume_attachment`), server power states and rebuilds (`server` with `state: started|stopped|rebuild`).

---

## Teardown safety

Any run where `hcloud_state: absent` or any per-resource `state: absent` (including load balancer services/targets and firewall `apply_to` entries) is detected will abort unless `-e hcloud_allow_teardown=true` is also passed. Scope destructive runs with `--tags` to avoid destroying everything at once:

```bash
ansible-playbook examples/teardown.yml \
  -e hcloud_allow_teardown=true \
  --tags servers,server_networks
```

The role deletes absent resources in reverse dependency order (load balancers, volumes, floating/primary IPs, server-network attachments, servers, placement groups, firewalls, subnetworks, networks, SSH keys) after creating or updating present ones, so a full teardown works in a single, re-runnable pass. Absent firewalls are detached from their remaining resources and assigned floating IPs are unassigned before deletion. See [`examples/teardown.yml`](examples/teardown.yml).

---

## Dynamic inventory hand-off (recommended)

After provisioning, use the `hetzner.hcloud` inventory plugin to automatically discover hosts by label. No static file to maintain:

```yaml
# hcloud.yml (inventory plugin config - the name must end in hcloud.yml)
plugin: hetzner.hcloud.hcloud        # token from HCLOUD_TOKEN
label_selector: managed-by=ansible-hetzner-cloud
network: prod-net
connect_with: private_ipv4           # ansible_host = private IP on 'network'
groups:
  server_nodes: "hcloud_labels.role | default('') == 'control-plane'"
  agent_nodes: "hcloud_labels.role | default('') == 'worker'"
  proxy_hosts: "hcloud_labels.role | default('') == 'proxy'"
  vault: "hcloud_labels.role | default('') == 'vault'"
```

The plugin prefixes every Hetzner field with `hcloud_`, so the labels are `hcloud_labels` (a bare `labels.role` silently matches nothing). This snippet ships as [`examples/inventory/hcloud.yml`](examples/inventory/hcloud.yml).

Label your servers with the `role` key in `hcloud_servers[].labels` using values `control-plane`, `worker`, `proxy`, or `vault`. The `groups:` map emits group names your downstream plays can target (`server_nodes`, `agent_nodes`, `proxy_hosts`, `vault`).

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for full inventory hand-off details.

---

## Offline testing

The `molecule/default/` scenario runs with `hcloud_provision: false` and requires **no HCLOUD_TOKEN**. It validates `validate.yml`, `preflight.yml`, and `argument_specs.yml` without making any API calls.

```bash
export PATH="$HOME/.venvs/ansible-roles/bin:$PATH"
molecule test -s default
```

`check_mode` is **not** a substitute for the offline gate — `hcloud.*` modules authenticate and query live state even under `--check`.

The `molecule/teardown-gate/` scenario is also fully offline (no `HCLOUD_TOKEN`). It proves the destructive-action safety gate fires: with `hcloud_state: absent` and `hcloud_allow_teardown: false`, the role must abort before any API call.

```bash
molecule test -s teardown-gate
```

The `molecule/mock-api/` scenario makes real `hetzner.hcloud` module calls against an in-memory stand-in of the Hetzner API on `127.0.0.1` (dummy token, no cloud resources) and asserts on the requests it receives: floating IP re-runs, scoped `--tags` runs, single-pass teardown, firewall bindings, server options, `--check` and the dynamic inventory snippet. It needs no Docker. Set `MOCK_HCLOUD_PORT` if port 18742 is taken.

```bash
molecule test -s mock-api
```

CI runs `default` (four distros, plus an ansible-core 2.22 leg), `teardown-gate` and `mock-api` on every pull request.

The `molecule/live/` scenario creates real Hetzner Cloud resources and requires `HCLOUD_TOKEN`. It is **not** part of default CI: run it locally or by hand through the `Live` workflow (`workflow_dispatch`, needs the `HCLOUD_TOKEN` secret). See [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) for usage.

---

## Examples

- [`examples/ha_cluster.yml`](examples/ha_cluster.yml) — full HA Kubernetes cluster topology (3 control-plane + 2 workers + private network + firewalls + floating IP)
- [`examples/teardown.yml`](examples/teardown.yml) - safe teardown walkthrough (single pass, reverse dependency order handled by the role)
- [`examples/inventory/hcloud.yml`](examples/inventory/hcloud.yml) - dynamic inventory plugin config that groups the role's servers by `role` label

---

## Inventory output

After provisioning, this role emits a labeled inventory — via the dynamic
`hetzner.hcloud` inventory plugin or an optional static file
(`hcloud_write_inventory: true`) — that your downstream plays consume by
group/label.

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for the inventory hand-off details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Code of Conduct

Read our [Code of Conduct](CODE_OF_CONDUCT.md).

## Changelog

See the [GitHub Releases](https://github.com/devopsgroupeu/ansible-role-hetzner-cloud/releases) page for release history.

## License

```
Copyright 2025 DevOpsGroup

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

> For more information or support, please refer to the official documentation or contact us at info@devopsgroup.sk
