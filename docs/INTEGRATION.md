# Integration

Guide for integrating `ansible-role-hetzner-cloud` with downstream roles and dynamic inventory.

---

## Table of Contents

- [Role chain overview](#role-chain-overview)
- [Dynamic inventory hand-off (recommended)](#dynamic-inventory-hand-off-recommended)
- [Static inventory fallback](#static-inventory-fallback)
- [Integration with ansible-role-rke2](#integration-with-ansible-role-rke2)
- [Integration with ansible-role-haproxy-keepalived](#integration-with-ansible-role-haproxy-keepalived)
- [Integration with ansible-role-hashicorp-vault](#integration-with-ansible-role-hashicorp-vault)
- [Full multi-play pipeline example](#full-multi-play-pipeline-example)

---

## Role chain overview

```
ansible-role-hetzner-cloud   (this role — controller-side, localhost)
        |
        | provisions: servers, networks, firewalls, floating IP
        v
ansible-role-haproxy-keepalived  (proxy_hosts — HA LB + VIP flip)
        |
        | provides: stable VIP for downstream services
        v
ansible-role-hashicorp-vault     (vault — Raft cluster behind VIP)
        |
        | provides: secrets management for rke2 join token, certs
        v
ansible-role-rke2             (server_nodes then agent_nodes — Kubernetes)
```

`hetzner-cloud` runs first (on `localhost`, `connection: local`). After it
completes, the other roles target the newly provisioned hosts in config-tier
order: haproxy/keepalived first (establishes the VIP), then vault (Raft cluster
behind the VIP), then rke2 (servers then agents). Hosts are discovered via the
dynamic inventory plugin or the static inventory written by `hcloud_write_inventory`.

### Inventory group contract

This role emits hosts into the following groups (via dynamic plugin `groups:` map
or the static template). Group names match exactly what each consumer role expects:

| Group | Label value | Consumer role |
|---|---|---|
| `server_nodes` | `role=control-plane` | `devopsgroupeu.rke2` (server play) |
| `agent_nodes` | `role=worker` | `devopsgroupeu.rke2` (agent play) |
| `proxy_hosts` | `role=proxy` | `devopsgroupeu.haproxy_keepalived` |
| `vault` | `role=vault` | `devopsgroupeu.hashicorp_vault` |

---

## Dynamic inventory hand-off (recommended)

After provisioning, use the `hetzner.hcloud.hcloud` inventory plugin to
automatically discover hosts by label. No static file to maintain; newly created
servers matching a label selector appear automatically.

Create a file named `hcloud.yml` (must end in `.hcloud.yml`) alongside your
playbooks:

```yaml
# hcloud.yml
plugin: hetzner.hcloud.hcloud
api_token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"

# Filter to only servers on your private network (recommended for multi-tenant projects)
network: prod-net

# Group hosts by label values — emit the consumer role's expected group names
groups:
  server_nodes: "labels.role == 'control-plane'"
  agent_nodes: "labels.role == 'worker'"
  proxy_hosts: "labels.role == 'proxy'"
  vault: "labels.role == 'vault'"

# Use private network IPs for SSH (requires network: above)
# hostvars_prefix defaults to 'hcloud_' since collection v5
compose:
  ansible_host: private_ipv4_address
```

Run with:
```bash
export HCLOUD_TOKEN="your-token"
ansible-inventory -i hcloud.yml --list
```

---

## Static inventory fallback

For air-gapped environments or CI pipelines that cannot use the dynamic plugin,
enable `hcloud_write_inventory: true` in your provisioning play. The role renders
`templates/hcloud_inventory.yml.j2` to `hcloud_inventory_path`:

```yaml
vars:
  hcloud_write_inventory: true
  hcloud_inventory_path: /tmp/hcloud_inventory.yml
```

The generated file groups servers by their `role` label using the consumer role
group names:

```yaml
all:
  children:
    server_nodes:
      hosts:
        cp-01:
          ansible_host: 10.0.1.11
    agent_nodes:
      hosts:
        wk-01:
          ansible_host: 10.0.1.21
    proxy_hosts:
      hosts:
        px-01:
          ansible_host: 10.0.1.31
    vault:
      hosts:
        vault-01:
          ansible_host: 10.0.1.41
```

Use the file in subsequent plays:
```bash
ansible-playbook site.yml -i /tmp/hcloud_inventory.yml
```

Note: the static inventory is generated from the `hcloud_provisioned_servers`
role fact set by `outputs.yml`. It only contains servers created in the same run
(not previously existing servers).

---

## Integration with ansible-role-rke2

`ansible-role-rke2` configures an RKE2 Kubernetes cluster on the hosts
provisioned by this role. It runs on the target hosts, not on localhost.

Label your servers so the dynamic inventory groups them correctly:

```yaml
# In your hetzner-cloud provisioning play
hcloud_servers:
  - name: cp-01
    labels:
      role: control-plane
      cluster: prod
  - name: wk-01
    labels:
      role: worker
      cluster: prod
```

Then run rke2 against the produced groups:

```yaml
- hosts: server_nodes
  roles:
    - devopsgroupeu.rke2

- hosts: agent_nodes
  vars:
    rke2_type: agent
  roles:
    - devopsgroupeu.rke2
```

The RKE2 join token and API endpoint are typically registered as facts in the
control-plane play and passed to worker plays. See the `ansible-role-rke2`
README for the full variable contract.

---

## Integration with ansible-role-haproxy-keepalived

`ansible-role-haproxy-keepalived` installs HAProxy + Keepalived on proxy nodes
and manages the floating IP VIP. Run this play **before** vault and rke2 so the
VIP is available when downstream roles need it.

1. Provision proxy servers and a floating IP in the hetzner-cloud play:

```yaml
hcloud_servers:
  - name: proxy-01
    server_type: cx22
    labels:
      role: proxy
      cluster: prod
  - name: proxy-02
    server_type: cx22
    labels:
      role: proxy
      cluster: prod

hcloud_floating_ips:
  - name: ingress-vip
    type: ipv4
    home_location: fsn1
    labels:
      role: vip
```

2. Run haproxy-keepalived on the proxy group, passing the floating IP address:

```yaml
- hosts: proxy_hosts
  vars:
    cloud_floating_ip_enabled: true
    cloud_api_endpoint: "https://api.hetzner.cloud/v1"
    cloud_api_token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"
    cloud_floating_ip_address: "{{ hostvars['proxy-01']['hcloud_floating_ip_ingress-vip'] | default('') }}"
    cloud_server_name: "{{ inventory_hostname }}"
    haproxy_loadbalancer_master: proxy-01
    haproxy_loadbalancer_backup: proxy-02
    haproxy_frontends:
      - name: k8s_api
        address: "*"
        port: 6443
        default_backend: k8s_api_servers
        mode: tcp
    haproxy_backends:
      - name: k8s_api_servers
        balance: roundrobin
        mode: tcp
        servers: "{{ groups['server_nodes'] | default([]) }}"
        port: 6443
        options:
          - check
  roles:
    - devopsgroupeu.haproxy_keepalived
```

Keepalived flips the floating IP between `proxy-01` and `proxy-02` on failure,
providing a stable VIP for downstream services.

---

## Integration with ansible-role-hashicorp-vault

`ansible-role-hashicorp-vault` installs a Raft HA Vault cluster on dedicated
vault nodes. Run this play **after** haproxy-keepalived so the VIP is available
as the `vault_api_addr` endpoint, and **before** rke2 so secrets are available
at cluster bootstrap.

1. Provision vault servers in the hetzner-cloud play:

```yaml
hcloud_servers:
  - name: vault-01
    server_type: cx22
    labels:
      role: vault
      cluster: prod
  - name: vault-02
    server_type: cx22
    labels:
      role: vault
      cluster: prod
  - name: vault-03
    server_type: cx22
    labels:
      role: vault
      cluster: prod
```

2. Run hashicorp-vault on the vault group, pointing the cluster API address at
   the HAProxy VIP:

```yaml
- hosts: vault
  vars:
    vault_version: "2.0.3"
    vault_cluster_name: prod-vault
    vault_api_addr: "https://{{ vip_address }}:8200"
    vault_raft_peers: "{{ groups['vault'] }}"
  roles:
    - devopsgroupeu.hashicorp_vault
```

See the `ansible-role-hashicorp-vault` README for the full variable contract
including TLS, unseal, and ESO integration.

---

## Full multi-play pipeline example

```yaml
# site.yml

# Play 1: Provision infra (controller-side)
- hosts: localhost
  connection: local
  gather_facts: false
  become: false
  vars:
    hcloud_api_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'hetzner/token').secret.value }}"
    hcloud_ssh_keys:
      - name: ops-key
        public_key: "{{ lookup('ansible.builtin.file', '~/.ssh/ops.pub') }}"
    hcloud_networks:
      - name: prod-net
        ip_range: "10.0.0.0/16"
    hcloud_subnetworks:
      - network: prod-net
        type: cloud
        network_zone: eu-central
        ip_range: "10.0.1.0/24"
    hcloud_servers:
      - name: proxy-01
        server_type: cx22
        location: fsn1
        ssh_keys: [ops-key]
        labels: {role: proxy, cluster: prod}
      - name: vault-01
        server_type: cx22
        location: fsn1
        ssh_keys: [ops-key]
        labels: {role: vault, cluster: prod}
      - name: cp-01
        server_type: cx32
        location: fsn1
        ssh_keys: [ops-key]
        labels: {role: control-plane, cluster: prod}
      - name: wk-01
        server_type: cx42
        location: fsn1
        ssh_keys: [ops-key]
        labels: {role: worker, cluster: prod}
    hcloud_floating_ips:
      - name: ingress-vip
        type: ipv4
        home_location: fsn1
  roles:
    - devopsgroupeu.hetzner_cloud

# Play 2: Install HAProxy + Keepalived (establishes the VIP)
# Use -i hcloud.yml (dynamic inventory) or -i /tmp/hcloud_inventory.yml (static)
- hosts: proxy_hosts
  roles:
    - devopsgroupeu.haproxy_keepalived

# Play 3: Install Vault (Raft cluster, behind the VIP)
- hosts: vault
  vars:
    vault_version: "2.0.3"
  roles:
    - devopsgroupeu.hashicorp_vault

# Play 4: Install RKE2 control-plane
- hosts: server_nodes
  vars:
    rke2_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'rke2/token').secret.value }}"
  roles:
    - devopsgroupeu.rke2

# Play 5: Join workers
- hosts: agent_nodes
  serial: 1
  vars:
    rke2_type: agent
  roles:
    - devopsgroupeu.rke2
```

Run with dynamic inventory (`hcloud.yml` is your hcloud inventory plugin config — you provide this file; see [hcloud inventory plugin docs](https://docs.ansible.com/ansible/latest/collections/hetzner/hcloud/hcloud_inventory.html)):

```bash
export HCLOUD_TOKEN="your-token"
ansible-playbook -i hcloud.yml site.yml
```

Or run with the static inventory generated by the role (written to `hcloud_inventory_path`), or adapt `examples/inventory/hcloud_static_example.yml` as a starting point:

```bash
ansible-playbook -i /tmp/hcloud_inventory.yml site.yml
```
