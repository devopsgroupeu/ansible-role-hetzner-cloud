# Architecture

Infrastructure topology and provisioning flow for `ansible-role-hetzner-cloud`.

---

## Provisioning flow

This role runs controller-side (`connection: local`, `become: false`). It makes
API calls to Hetzner Cloud to create resources, then emits an inventory so
downstream config-tier roles can target the newly provisioned hosts.

```mermaid
flowchart TD
    subgraph Controller["Ansible Controller (localhost)"]
        play["Play 1: hetzner-cloud role"]
    end

    subgraph HCloud["Hetzner Cloud Project"]
        net["Private network<br/>prod-net 10.0.0.0/16"]
        fip["Floating IP<br/>ingress-vip"]

        subgraph proxy_group["proxy_hosts (role=proxy)"]
            px1["proxy-01<br/>HAProxy + Keepalived"]
            px2["proxy-02<br/>HAProxy + Keepalived"]
        end

        subgraph vault_group["vault (role=vault)"]
            v1["vault-01"]
            v2["vault-02"]
            v3["vault-03"]
        end

        subgraph cp_group["server_nodes (role=control-plane)"]
            cp1["cp-01<br/>RKE2 server"]
            cp2["cp-02<br/>RKE2 server"]
            cp3["cp-03<br/>RKE2 server"]
        end

        subgraph wk_group["agent_nodes (role=worker)"]
            wk1["wk-01<br/>RKE2 agent"]
            wk2["wk-02<br/>RKE2 agent"]
        end
    end

    subgraph Inventory["Inventory hand-off"]
        inv["hcloud.yml plugin<br/>or hcloud_inventory.yml.j2"]
    end

    subgraph DownstreamRoles["Config-tier roles (subsequent plays)"]
        r_haproxy["devopsgroupeu.haproxy-keepalived<br/>hosts: proxy_hosts"]
        r_vault["devopsgroupeu.hashicorp-vault<br/>hosts: vault"]
        r_rke2_srv["devopsgroupeu.rke2<br/>hosts: server_nodes"]
        r_rke2_agent["devopsgroupeu.rke2<br/>hosts: agent_nodes"]
    end

    play -->|"creates"| net
    play -->|"creates"| fip
    play -->|"creates"| proxy_group
    play -->|"creates"| vault_group
    play -->|"creates"| cp_group
    play -->|"creates"| wk_group
    play -->|"emits groups"| inv

    inv -->|"server_nodes"| r_rke2_srv
    inv -->|"agent_nodes"| r_rke2_agent
    inv -->|"proxy_hosts"| r_haproxy
    inv -->|"vault"| r_vault

    r_haproxy -->|"VIP established"| r_vault
    r_vault -->|"secrets available"| r_rke2_srv
    r_rke2_srv -->|"cluster bootstrapped"| r_rke2_agent
```

---

## Inventory group contract

The role assigns servers to inventory groups based on the `role` label applied
at server creation time. Label *values* are fixed; group *names* are the
consumer roles' expected names:

| Hetzner label | Inventory group | Consumer role |
|---|---|---|
| `role=control-plane` | `server_nodes` | `devopsgroupeu.rke2` |
| `role=worker` | `agent_nodes` | `devopsgroupeu.rke2` |
| `role=proxy` | `proxy_hosts` | `devopsgroupeu.haproxy-keepalived` |
| `role=vault` | `vault` | `devopsgroupeu.hashicorp-vault` |

The dynamic inventory plugin (`hcloud.yml`) uses a `groups:` map to produce
these names. The static template (`templates/hcloud_inventory.yml.j2`) uses
the same mapping. Either hand-off produces an inventory that downstream roles
consume without modification.

---

## Resource creation order

Resources are created in dependency order within a single play:

1. SSH keys
2. Networks → subnetworks
3. Firewalls
4. Placement groups
5. Servers (reference SSH keys, firewalls, placement groups)
6. Server-network attachments (reference servers and networks)
7. Primary IPs / floating IPs
8. Volumes
9. Load balancers (optional, alternative to self-hosted HAProxy)
10. Outputs: set `hcloud_provisioned_servers` fact; render static inventory

---

## Config-tier stack order

The downstream plays form a config-tier dependency chain:

```
hetzner-cloud (provision)
    → haproxy-keepalived (VIP)
        → hashicorp-vault (Raft behind VIP)
            → rke2 servers
                → rke2 agents (serial: 1)
                    → in-cluster ESO / Vault Agent
```

Vault must come after haproxy because the Vault `vault_api_addr` points at the
HAProxy VIP. RKE2 must come after vault so the join token and TLS secrets are
available from Vault at cluster bootstrap.
