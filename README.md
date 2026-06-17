# ansible-role-hetzner-cloud

**Namespace:** `devopsgroupeu` | **Role:** `hetzner_cloud` | **License:** Apache-2.0

Controller-side Ansible role that provisions Hetzner Cloud infrastructure (SSH keys, networks, subnetworks, firewalls, placement groups, servers, server-network attachments, primary IPs, floating IPs, volumes, and load balancers) via the [`hetzner.hcloud`](https://galaxy.ansible.com/hetzner/hcloud) collection.

**Default posture: does nothing.** Every resource list defaults to `[]`. The role is a no-op until you populate the lists.

---

## Controller-side execution

This role runs on the **Ansible control node** (your workstation or CI runner), not on the target hosts. Example play:

```yaml
- hosts: localhost
  connection: local
  gather_facts: false
  become: false
  vars:
    hcloud_api_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'hetzner/token').secret.value }}"
    hcloud_servers:
      - name: cp-01
        server_type: cx32
        image: debian-12
        location: nbg1
        labels: {role: control-plane, cluster: prod}
  roles:
    - devopsgroupeu.hetzner_cloud
```

---

## Requirements

### Collection

```bash
ansible-galaxy collection install -r requirements.yml
```

`requirements.yml`:

```yaml
collections:
  - name: hetzner.hcloud
    version: ">=4.0.0"
```

### Python

```bash
pip install -r requirements.txt
```

The `hcloud` Python SDK is vendored inside the `hetzner.hcloud` collection since v1.16 (Python 3.10+ required). The `hcloud>=2.0.0` entry in `requirements.txt` is listed for explicit clarity.

---

## Authentication

Never hardcode the API token. Use one of:

1. **Environment variable (recommended for CI):**
   ```bash
   export HCLOUD_TOKEN="<your-token>"
   ```

2. **HashiCorp Vault (recommended for production):**
   ```yaml
   hcloud_api_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'hetzner/token').secret.value }}"
   ```

3. **Ansible Vault:**
   ```yaml
   hcloud_api_token: "{{ vault_hcloud_token }}"
   ```

The `hcloud_api_token` variable defaults to `lookup('ansible.builtin.env', 'HCLOUD_TOKEN')`. If it resolves to an empty string and `hcloud_provision: true`, the role aborts with a clear error.

---

## Variable contract

All tunables are prefixed `hcloud_*`. Full documented defaults are in `defaults/main.yml`. The table below lists top-level variables; per-item sub-keys are documented in `meta/argument_specs.yml`.

| Variable | Type | Default | Description |
|---|---|---|---|
| `hcloud_api_token` | str | `$HCLOUD_TOKEN` | API token — source from Vault/env, never hardcode |
| `hcloud_provision` | bool | `true` | Master gate — set `false` for offline/validate-only runs |
| `hcloud_state` | str | `present` | Global default state (`present`\|`absent`) |
| `hcloud_allow_teardown` | bool | `false` | Hard guard — must be `true` to allow any `state: absent` |
| `hcloud_no_log` | bool | `true` | Suppress sensitive output; set `false` for debugging only |
| `hcloud_default_location` | str | `fsn1` | Fallback location slug for servers/IPs |
| `hcloud_default_image` | str | `debian-12` | Fallback OS image for servers |
| `hcloud_managed_label_key` | str | `managed-by` | Label key stamped on every created resource |
| `hcloud_managed_label_value` | str | `ansible-hetzner-cloud` | Label value paired with the managed-by key |
| `hcloud_write_inventory` | bool | `false` | Write a static INI inventory to `hcloud_inventory_path` |
| `hcloud_inventory_path` | str | `""` | Destination for the static inventory (required if `hcloud_write_inventory: true`) |
| `hcloud_ssh_keys` | list[dict] | `[]` | SSH keys to upload |
| `hcloud_networks` | list[dict] | `[]` | Private networks |
| `hcloud_subnetworks` | list[dict] | `[]` | Subnets within networks |
| `hcloud_firewalls` | list[dict] | `[]` | Firewall rules |
| `hcloud_placement_groups` | list[dict] | `[]` | Anti-affinity groups |
| `hcloud_servers` | list[dict] | `[]` | Compute instances |
| `hcloud_server_networks` | list[dict] | `[]` | Server-network attachments |
| `hcloud_primary_ips` | list[dict] | `[]` | Stable pre-created public IPs |
| `hcloud_floating_ips` | list[dict] | `[]` | Floating IPs (e.g. HA VIP for haproxy-keepalived) |
| `hcloud_volumes` | list[dict] | `[]` | Block storage volumes |
| `hcloud_load_balancers` | list[dict] | `[]` | Managed load balancers (off by default) |

---

## Teardown safety

Any run where `hcloud_state: absent` or any per-resource `state: absent` is detected will abort unless `-e hcloud_allow_teardown=true` is also passed. Scope destructive runs with `--tags`:

```bash
ansible-playbook teardown.yml \
  -e hcloud_allow_teardown=true \
  --tags servers,server_networks
```

---

## Dynamic inventory hand-off (recommended)

After provisioning, use the `hetzner.hcloud` dynamic inventory plugin so downstream roles (`rke2`, `haproxy-keepalived`) target hosts by label selector — no static file to maintain:

```yaml
# hcloud.yml (inventory plugin config)
plugin: hetzner.hcloud.hcloud
api_token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"
network: openprime-net
keyed_groups:
  - key: labels.role
    prefix: role
  - key: labels.cluster
    prefix: cluster
```

Run `ansible-role-rke2` against `role_control_plane` / `role_worker` groups.

---

## Offline testing

The `molecule/default/` scenario runs with `hcloud_provision: false` and requires **no HCLOUD_TOKEN**. It validates `validate.yml`, `preflight.yml`, and `argument_specs.yml` without making any API calls.

```bash
export PATH="$HOME/.venvs/ansible-roles/bin:$PATH"
molecule test -s default
```

`check_mode` is **not** a substitute for the offline gate — `hcloud.*` modules authenticate and query live state even under `--check`.

---

## Examples

See `examples/rke2_cluster.yml` for a full HA RKE2 topology (3 control-plane + 2 workers + private network + firewall + floating IP) and `examples/teardown.yml` for a safe teardown walkthrough.

---

## Integration with sibling roles

1. `devopsgroupeu.hetzner_cloud` — provisions infrastructure (this role)
2. `devopsgroupeu.rke2` — installs RKE2 on the provisioned servers
3. `devopsgroupeu.haproxy_keepalived` — configures HA load balancing with the floating IP
