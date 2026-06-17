# Integration

Guide for integrating `ansible-role-hetzner-cloud` with downstream roles and dynamic inventory.

---

## Table of Contents

- [Role chain overview](#role-chain-overview)
- [Dynamic inventory hand-off (recommended)](#dynamic-inventory-hand-off-recommended)
- [Static inventory fallback](#static-inventory-fallback)
- [Integration with ansible-role-rke2](#integration-with-ansible-role-rke2)
- [Integration with ansible-role-haproxy-keepalived](#integration-with-ansible-role-haproxy-keepalived)
- [Full multi-play pipeline example](#full-multi-play-pipeline-example)

---

## Role chain overview

```
ansible-role-hetzner-cloud  (this role — controller-side, localhost)
        |
        | provisions: servers, networks, firewalls, floating IP
        v
ansible-role-rke2           (runs on provisioned hosts — installs RKE2)
        |
        | on control-plane nodes
        v
ansible-role-haproxy-keepalived  (runs on proxy nodes — HA LB + VIP flip)
```

`hetzner-cloud` runs first (on `localhost`, `connection: local`). After it completes, the other roles target the newly provisioned hosts — discovered either via the dynamic inventory plugin or the static inventory written by `hcloud_write_inventory`.

---

## Dynamic inventory hand-off (recommended)

After provisioning, use the `hetzner.hcloud.hcloud` inventory plugin to automatically discover hosts by label. No static file to maintain; newly created servers matching a label selector appear automatically.

Create a file named `hcloud.yml` (must end in `.hcloud.yml`) alongside your playbooks:

```yaml
# hcloud.yml
plugin: hetzner.hcloud.hcloud
api_token: "{{ lookup('env', 'HCLOUD_TOKEN') }}"

# Filter to only servers on your private network (recommended for multi-tenant projects)
network: prod-net

# Group hosts by label values
keyed_groups:
  - key: labels.role
    prefix: role
    separator: "_"
  - key: labels.cluster
    prefix: cluster
    separator: "_"

# Use private network IPs for SSH (requires network: above)
# hostvars_prefix defaults to 'hcloud_' since collection v5
compose:
  ansible_host: private_ipv4_address
```

This produces groups such as `role_control_plane`, `role_worker`, `role_proxy` based on the labels set in `hcloud_servers[].labels`.

Run with:
```bash
export HCLOUD_TOKEN="your-token"
ansible-inventory -i hcloud.yml --list
```

---

## Static inventory fallback

For air-gapped environments or CI pipelines that cannot use the dynamic plugin, enable `hcloud_write_inventory: true` in your provisioning play. The role renders `templates/hcloud_inventory.ini.j2` to `hcloud_inventory_path`:

```yaml
vars:
  hcloud_write_inventory: true
  hcloud_inventory_path: /tmp/hcloud_inventory.ini
```

The generated file groups servers by their `role` label:

```ini
[control_plane]
cp-01 ansible_host=10.0.1.11
cp-02 ansible_host=10.0.1.12

[workers]
wk-01 ansible_host=10.0.1.21

[proxy]
# (empty if no role=proxy servers were provisioned)
```

Use the file in subsequent plays:
```bash
ansible-playbook rke2.yml -i /tmp/hcloud_inventory.ini
```

Note: the static inventory is generated from the `hcloud_provisioned_servers` role fact set by `outputs.yml`. It only contains servers created in the same run (not previously existing servers).

---

## Integration with ansible-role-rke2

`ansible-role-rke2` configures an RKE2 Kubernetes cluster on the hosts provisioned by this role. It runs on the target hosts, not on localhost.

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
- hosts: role_control_plane
  roles:
    - devopsgroupeu.rke2

- hosts: role_worker
  roles:
    - devopsgroupeu.rke2
```

The RKE2 join token and API endpoint are typically registered as facts in the control-plane play and passed to worker plays. See the `ansible-role-rke2` README for the full variable contract.

---

## Integration with ansible-role-haproxy-keepalived

`ansible-role-haproxy-keepalived` installs HAProxy + Keepalived on proxy nodes and manages the floating IP VIP.

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
- hosts: role_proxy
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
        default_backend: k8s_masters
        mode: tcp
    haproxy_backends:
      - name: k8s_masters
        balance: roundrobin
        mode: tcp
        servers: "{{ groups['role_control_plane'] }}"
        port: 6443
        options:
          - check
  roles:
    - devopsgroupeu.haproxy_keepalived
```

Keepalived flips the floating IP between `proxy-01` and `proxy-02` on failure, providing a stable VIP for the Kubernetes API endpoint.

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
    hcloud_server_networks:
      - server: cp-01
        network: prod-net
        ip: "10.0.1.11"
      - server: wk-01
        network: prod-net
        ip: "10.0.1.21"
    hcloud_floating_ips:
      - name: ingress-vip
        type: ipv4
        home_location: fsn1
  roles:
    - devopsgroupeu.hetzner_cloud

# Play 2: Install RKE2 control-plane
# Use -i hcloud.yml (dynamic inventory) or -i /tmp/hcloud_inventory.ini (static)
- hosts: role_control_plane
  vars:
    rke2_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'rke2/token').secret.value }}"
  roles:
    - devopsgroupeu.rke2

# Play 3: Join workers
- hosts: role_worker
  vars:
    rke2_type: agent
  roles:
    - devopsgroupeu.rke2
```

Run with dynamic inventory:

```bash
export HCLOUD_TOKEN="your-token"
ansible-playbook -i hcloud.yml site.yml
```
