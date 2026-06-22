# Configuration Reference

Full variable reference for the `ansible-role-hetzner-cloud` role. All variables are defined with defaults in [`defaults/main.yml`](../defaults/main.yml). Every variable listed here has a corresponding entry in [`meta/argument_specs.yml`](../meta/argument_specs.yml).

---

## Table of Contents

- [Auth](#auth)
- [Global behaviour](#global-behaviour)
- [SSH Keys](#ssh-keys-hcloud_ssh_keys)
- [Networks](#networks-hcloud_networks)
- [Subnetworks](#subnetworks-hcloud_subnetworks)
- [Firewalls](#firewalls-hcloud_firewalls)
- [Placement Groups](#placement-groups-hcloud_placement_groups)
- [Servers](#servers-hcloud_servers)
- [Server-Network Attachments](#server-network-attachments-hcloud_server_networks)
- [Primary IPs](#primary-ips-hcloud_primary_ips)
- [Floating IPs](#floating-ips-hcloud_floating_ips)
- [Volumes](#volumes-hcloud_volumes)
- [Load Balancers](#load-balancers-hcloud_load_balancers)

---

## Auth

| Variable | Type | Default | Required | Description |
|---|---|---|---|---|
| `hcloud_api_token` | str | `$HCLOUD_TOKEN` | No | API token for the Hetzner Cloud API. Resolved from the `HCLOUD_TOKEN` environment variable when not set. Source from HashiCorp Vault or Ansible Vault. Never hardcode. |

Token resolution order (first non-empty wins):
1. `hcloud_api_token` explicitly passed (e.g. from `lookup('community.hashi_vault.vault_kv2_get', ...)`)
2. `HCLOUD_TOKEN` environment variable

An empty token aborts the role with a clear error when `hcloud_provision: true`.

---

## Global behaviour

| Variable | Type | Default | Required | Description |
|---|---|---|---|---|
| `hcloud_provision` | bool | `true` | No | Master kill-switch. Set `false` to skip all `hetzner.hcloud.*` API tasks (offline/validate-only mode). The offline molecule scenario relies on this. |
| `hcloud_state` | str | `present` | No | Global default state for all resources. `present` or `absent`. Per-resource `state:` overrides this. |
| `hcloud_allow_teardown` | bool | `false` | No | Hard guard against accidental destruction. Any resource with `state: absent` aborts unless this is `true`. Pass as `-e hcloud_allow_teardown=true` on CLI. |
| `hcloud_no_log` | bool | `true` | No | Suppress task output that may contain the API token or cloud-init join tokens. Set `false` temporarily for debugging. |
| `hcloud_default_location` | str | `fsn1` | No | Fallback Hetzner Cloud location slug for servers and primary IPs when not specified per-resource. |
| `hcloud_default_image` | str | `debian-12` | No | Fallback OS image for servers when not specified per-resource. |
| `hcloud_managed_label_key` | str | `managed-by` | No | Label key stamped on every created resource to identify what this role owns and enable dynamic inventory grouping. |
| `hcloud_managed_label_value` | str | `ansible-hetzner-cloud` | No | Label value paired with `hcloud_managed_label_key` on all created resources. |
| `hcloud_write_inventory` | bool | `false` | No | When `true`, renders `templates/hcloud_inventory.ini.j2` to `hcloud_inventory_path`. Useful for pipelines without a dynamic inventory plugin. |
| `hcloud_inventory_path` | str | `""` | No | Destination file path for the rendered static inventory. Required (non-empty) when `hcloud_write_inventory: true`. |

---

## SSH Keys (`hcloud_ssh_keys`)

List of SSH public key dicts to upload to Hetzner Cloud.

```yaml
hcloud_ssh_keys:
  - name: ops-key
    public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/ops.pub') }}"
    labels:
      team: platform
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | SSH key name (unique identifier in Hetzner Cloud). |
| `public_key` | str | No | SSH public key string. Required when `state: present`. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. Defaults to `hcloud_state`. |

---

## Networks (`hcloud_networks`)

Private RFC1918 networks for node-to-node traffic and RKE2 CNI.

```yaml
hcloud_networks:
  - name: prod-net
    ip_range: "10.0.0.0/16"
    labels:
      cluster: prod
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Network name. |
| `ip_range` | str | No | CIDR block for the network. Required when `state: present`. |
| `expose_routes_to_vswitch` | bool | No | Expose routes to the vSwitch connected to this network. Only relevant when subnets of type `vswitch` are attached. |
| `delete_protection` | bool | No | Prevent accidental deletion of this network. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

---

## Subnetworks (`hcloud_subnetworks`)

Subnets within private networks. Parent network must already exist.

```yaml
hcloud_subnetworks:
  - network: prod-net
    type: cloud
    network_zone: eu-central
    ip_range: "10.0.1.0/24"
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `network` | str | Yes | Parent network name. |
| `type` | str | Yes | Subnet type: `cloud`, `server`, or `vswitch`. |
| `network_zone` | str | Yes | Network zone (e.g. `eu-central`). |
| `ip_range` | str | Yes | CIDR block for this subnet. |
| `vswitch_id` | int | No | vSwitch ID (required when `type: vswitch`). |
| `state` | str | No | Per-resource state override. |

---

## Firewalls (`hcloud_firewalls`)

Firewall resources with embedded rules and optional label-selector bindings.

```yaml
hcloud_firewalls:
  - name: k8s-cp-fw
    rules:
      - direction: in
        protocol: tcp
        port: "6443"
        source_ips:
          - "0.0.0.0/0"
          - "::/0"
        description: kube-apiserver
    apply_to:
      - label_selector: "role=control-plane"
    labels:
      cluster: prod
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Firewall name. |
| `rules` | list[dict] | No | List of firewall rule dicts (see below). |
| `apply_to` | list[dict] | No | Label-selector or server bindings to auto-attach the firewall to. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

Firewall rule sub-keys:

| Key | Values | Description |
|---|---|---|
| `direction` | `in` / `out` | Traffic direction. |
| `protocol` | `tcp`, `udp`, `icmp`, `esp`, `gre` | Protocol. |
| `port` | `"443"` / `"1024-5000"` | Port or range (for `tcp`/`udp`). |
| `source_ips` | list[str] | CIDR list (for `in` rules). |
| `destination_ips` | list[str] | CIDR list (for `out` rules). |
| `description` | str | Human-readable label. |

---

## Placement Groups (`hcloud_placement_groups`)

Anti-affinity groups for HA control-plane nodes.

```yaml
hcloud_placement_groups:
  - name: cp-spread
    type: spread
    labels:
      cluster: prod
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Placement group name. |
| `type` | str | Yes | Placement strategy. Only `spread` is available. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

---

## Servers (`hcloud_servers`)

Compute instances. SSH key, firewall, and network resources must be created before servers.

```yaml
hcloud_servers:
  - name: cp-01
    server_type: cx32
    image: debian-12
    location: fsn1
    ssh_keys:
      - ops-key
    firewalls:
      - k8s-cp-fw
    placement_group: cp-spread
    enable_ipv4: true
    enable_ipv6: false
    backups: false
    labels:
      role: control-plane
      cluster: prod
    state: present
```

| Sub-key | Type | Default | Required | Description |
|---|---|---|---|---|
| `name` | str | — | Yes | Server name (unique in the project). |
| `server_type` | str | — | No | Server type slug (e.g. `cx22`, `cx32`, `cx42`). Required when `state: present`. |
| `image` | str | `hcloud_default_image` | No | OS image slug. |
| `location` | str | `hcloud_default_location` | No | Location slug. Use `location`, not the deprecated `datacenter` (removal after 2026-07-01). |
| `ssh_keys` | list[str] | `[]` | No | SSH key names to associate at creation time (create-time only). |
| `firewalls` | list[str] | `[]` | No | Firewall names to apply. |
| `placement_group` | str | — | No | Placement group name for anti-affinity scheduling. |
| `volumes` | list[str] | `[]` | No | Volume names/IDs to attach at creation time. |
| `user_data` | str | — | No | Cloud-init user-data string. May contain join tokens; protected by `no_log`. |
| `enable_ipv4` | bool | `true` | No | Assign a public IPv4 address. |
| `enable_ipv6` | bool | `false` | No | Assign a public IPv6 address. |
| `backups` | bool | `false` | No | Enable automatic backups. |
| `labels` | dict | `{}` | No | Labels. The managed-by label is always merged. Use `role`/`cluster` labels for dynamic inventory grouping. |
| `state` | str | `hcloud_state` | No | Per-resource state override. |

---

## Server-Network Attachments (`hcloud_server_networks`)

Attach servers to private networks with optional fixed private IPs.

```yaml
hcloud_server_networks:
  - server: cp-01
    network: prod-net
    ip: "10.0.1.11"
    alias_ips: []
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `server` | str | Yes | Server name to attach. |
| `network` | str | Yes | Network name to attach to. Both must already exist. |
| `ip` | str | No | Fixed private IP within the subnet. |
| `alias_ips` | list[str] | No | Additional private IPs aliased to this attachment. |
| `state` | str | No | Per-resource state override. |

---

## Primary IPs (`hcloud_primary_ips`)

Pre-created stable public IPs that survive server rebuild/deletion.

```yaml
hcloud_primary_ips:
  - name: cp-01-ipv4
    type: ipv4
    location: fsn1
    auto_delete: false
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Primary IP name. |
| `type` | str | Yes | IP version: `ipv4` or `ipv6`. |
| `location` | str | No | Location slug. Required when `state: present` and no assignee set. Use `location` not `datacenter` (deprecated, removal 2026-07-01). |
| `assignee_type` | str | No | Resource type the IP is assigned to (e.g. `server`). Optional as of collection v6.9.0. |
| `assignee_id` | int | No | Server ID to pre-assign this IP to. |
| `auto_delete` | bool | No | Delete this IP when unassigned from its server. |
| `delete_protection` | bool | No | Prevent accidental deletion. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

---

## Floating IPs (`hcloud_floating_ips`)

Location-scoped floating IPs, e.g. the HA VIP managed by `haproxy-keepalived`.

```yaml
hcloud_floating_ips:
  - name: ingress-vip
    type: ipv4
    home_location: fsn1
    labels:
      role: vip
      cluster: prod
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Floating IP name. |
| `type` | str | Yes | IP version: `ipv4` or `ipv6`. |
| `home_location` | str | No | Location slug to anchor the IP to. Required when `state: present` unless `server` is set. |
| `server` | str | No | Server name to assign the floating IP to initially. `haproxy-keepalived` reassigns it during failover. |
| `description` | str | No | Human-readable description. |
| `delete_protection` | bool | No | Prevent accidental deletion. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

---

## Volumes (`hcloud_volumes`)

Persistent block storage volumes.

```yaml
hcloud_volumes:
  - name: vault-data
    size: 20
    location: fsn1
    format: ext4
    automount: false
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Volume name. |
| `size` | int | No | Volume size in GB. Required when `state: present`. |
| `location` | str | No | Location slug. Required when `state: present` and `server` is not set. |
| `server` | str | No | Server name to attach this volume to. Use `volume_attachment` module for post-creation attach/detach. |
| `format` | str | No | Filesystem to format at creation time (`ext4` or `xfs`). Applied once only. |
| `automount` | bool | No | Automatically mount the volume on the server. |
| `delete_protection` | bool | No | Prevent accidental deletion. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `state` | str | No | Per-resource state override. |

---

## Load Balancers (`hcloud_load_balancers`)

Managed load balancers — an alternative to self-hosted HAProxy. Off by default.

```yaml
hcloud_load_balancers:
  - name: api-lb
    load_balancer_type: lb11
    location: fsn1
    network: prod-net
    labels:
      cluster: prod
    services:
      - protocol: tcp
        listen_port: 6443
        destination_port: 6443
    targets:
      - type: label_selector
        label_selector: "role=control-plane"
        use_private_ip: true
    state: present
```

| Sub-key | Type | Required | Description |
|---|---|---|---|
| `name` | str | Yes | Load balancer name. |
| `load_balancer_type` | str | No | Type slug (e.g. `lb11`). Required when `state: present`. |
| `location` | str | No | Location slug. Required when `state: present` unless `network_zone` is given. |
| `network_zone` | str | No | Network zone slug (e.g. `eu-central`). Alternative to `location` for placing the load balancer. |
| `algorithm` | str | No | Load balancing algorithm: `round_robin` (default) or `least_connections`. |
| `delete_protection` | bool | No | Prevent accidental deletion of this load balancer. |
| `network` | str | No | Private network name to attach the load balancer to for private IP routing. |
| `labels` | dict | No | Arbitrary key/value labels. |
| `services` | list[dict] | No | Service definitions (protocol, listen_port, destination_port). Each becomes a `load_balancer_service` task. |
| `targets` | list[dict] | No | Target definitions (type, label_selector/server, use_private_ip). Each becomes a `load_balancer_target` task. |
| `state` | str | No | Per-resource state override. |
