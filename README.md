# ansible-role-hetzner-cloud

[![Ansible Galaxy](https://img.shields.io/badge/Ansible%20Galaxy-devopsgroupeu.hetzner--cloud-blue?logo=ansible)](https://galaxy.ansible.com/ui/standalone/roles/devopsgroupeu/hetzner-cloud/)

**Namespace:** `devopsgroupeu` | **Role:** `hetzner_cloud` | **License:** Apache-2.0

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

This is different from the config roles (`rke2`, `haproxy-keepalived`) which run on the provisioned hosts.

---

## Installation

Pull this role into your playbook project via a `requirements.yml` git source:

```yaml
roles:
  - name: devopsgroupeu.hetzner-cloud
    src: https://github.com/devopsgroupeu/ansible-role-hetzner-cloud
    scm: git
    version: "v1.0.0"
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
    version: ">=6.9.0"
```

### Python

```bash
pip install -r requirements.txt
```

The `hcloud` Python SDK is vendored inside the `hetzner.hcloud` collection since v1.16 (Python 3.10+ required). The `hcloud>=2.0.0` entry in `requirements.txt` is listed for explicit clarity.

> **Version note:** `requirements.yml` pins `hetzner.hcloud >= 6.9.0` as a minimum.
> Some optional fields used by this role (e.g. `primary_ip.assignee_type`) require
> `>= 6.9.0`. A recent collection version is strongly recommended.

---

## Authentication

Never hardcode the API token in a vars file or role. Use one of:

1. **Environment variable (CI / workstation):**
   ```bash
   export HCLOUD_TOKEN="your-api-token"
   ```

2. **HashiCorp Vault (recommended for production — Lukas's stack):**
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

### Resource lists (all default to `[]`)

| Variable | Type | Default | Description |
|---|---|---|---|
| `hcloud_ssh_keys` | list[dict] | `[]` | SSH keys to upload. Required sub-keys: `name`. |
| `hcloud_networks` | list[dict] | `[]` | Private networks. Required sub-keys: `name`, `ip_range`. |
| `hcloud_subnetworks` | list[dict] | `[]` | Subnets within networks. Required sub-keys: `network`, `type`, `network_zone`, `ip_range`. |
| `hcloud_firewalls` | list[dict] | `[]` | Firewall rules. Required sub-keys: `name`. |
| `hcloud_placement_groups` | list[dict] | `[]` | Anti-affinity groups. Required sub-keys: `name`, `type` (`spread`). |
| `hcloud_servers` | list[dict] | `[]` | Compute instances. Required sub-keys: `name`, `server_type` (when `state: present`). |
| `hcloud_server_networks` | list[dict] | `[]` | Server-network attachments. Required sub-keys: `server`, `network`. |
| `hcloud_primary_ips` | list[dict] | `[]` | Stable pre-created public IPs. Required sub-keys: `name`, `type`. |
| `hcloud_floating_ips` | list[dict] | `[]` | Floating IPs (e.g. HA VIP for haproxy-keepalived). Required sub-keys: `name`, `type`. |
| `hcloud_volumes` | list[dict] | `[]` | Block storage volumes. Required sub-keys: `name`, `size`. |
| `hcloud_load_balancers` | list[dict] | `[]` | Managed load balancers (off by default). Required sub-keys: `name`, `load_balancer_type`. |

Full per-item sub-key documentation is in [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md).

---

## Teardown safety

Any run where `hcloud_state: absent` or any per-resource `state: absent` is detected will abort unless `-e hcloud_allow_teardown=true` is also passed. Scope destructive runs with `--tags` to avoid destroying everything at once:

```bash
ansible-playbook examples/teardown.yml \
  -e hcloud_allow_teardown=true \
  --tags servers,server_networks
```

See [`examples/teardown.yml`](examples/teardown.yml) for the correct reverse-dependency teardown order.

---

## Dynamic inventory hand-off (recommended)

After provisioning, use the `hetzner.hcloud` inventory plugin to automatically discover hosts by label. No static file to maintain:

```yaml
# hcloud.yml (inventory plugin config — name must end in .hcloud.yml)
plugin: hetzner.hcloud.hcloud
api_token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"
network: prod-net
groups:
  server_nodes: "labels.role == 'control-plane'"
  agent_nodes: "labels.role == 'worker'"
  proxy_hosts: "labels.role == 'proxy'"
  vault: "labels.role == 'vault'"
compose:
  ansible_host: private_ipv4_address
```

Label your servers with the `role` key in `hcloud_servers[].labels` using values `control-plane`, `worker`, `proxy`, or `vault`. The `groups:` map emits the exact group names that each downstream role expects (`server_nodes`, `agent_nodes`, `proxy_hosts`, `vault`).

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for full integration details including the haproxy-keepalived floating IP setup.

---

## Offline testing

The `molecule/default/` scenario runs with `hcloud_provision: false` and requires **no HCLOUD_TOKEN**. It validates `validate.yml`, `preflight.yml`, and `argument_specs.yml` without making any API calls.

```bash
export PATH="$HOME/.venvs/ansible-roles/bin:$PATH"
molecule test -s default
```

`check_mode` is **not** a substitute for the offline gate — `hcloud.*` modules authenticate and query live state even under `--check`.

The `molecule/live/` scenario creates real Hetzner Cloud resources and requires `HCLOUD_TOKEN`. It is **not** part of default CI — see [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) for usage.

---

## Examples

- [`examples/rke2_cluster.yml`](examples/rke2_cluster.yml) — full HA RKE2 topology (3 control-plane + 2 workers + private network + firewalls + floating IP)
- [`examples/teardown.yml`](examples/teardown.yml) — safe teardown walkthrough with correct reverse-dependency ordering

---

## Integration with sibling roles

Config-tier order — each role depends on the one above it:

1. `devopsgroupeu.hetzner-cloud` — provisions Hetzner Cloud infrastructure (this role, runs on `localhost`)
2. `devopsgroupeu.haproxy-keepalived` — configures HA load balancing + floating IP VIP (runs on `proxy_hosts`; label `role=proxy`)
3. `devopsgroupeu.hashicorp-vault` — installs a Raft HA Vault cluster behind the VIP (runs on `vault`; label `role=vault`)
4. `devopsgroupeu.rke2` — installs RKE2 servers then agents (runs on `server_nodes` / `agent_nodes`; labels `role=control-plane` / `role=worker`)

See [`docs/INTEGRATION.md`](docs/INTEGRATION.md) for the full multi-play pipeline and dynamic inventory setup.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Code of Conduct

Read our [Code of Conduct](CODE_OF_CONDUCT.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for release history.

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
