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
            px1["proxy-01<br/>load balancer"]
            px2["proxy-02<br/>load balancer"]
        end

        subgraph vault_group["vault (role=vault)"]
            v1["vault-01"]
            v2["vault-02"]
            v3["vault-03"]
        end

        subgraph cp_group["server_nodes (role=control-plane)"]
            cp1["cp-01<br/>control-plane node"]
            cp2["cp-02<br/>control-plane node"]
            cp3["cp-03<br/>control-plane node"]
        end

        subgraph wk_group["agent_nodes (role=worker)"]
            wk1["wk-01<br/>worker node"]
            wk2["wk-02<br/>worker node"]
        end
    end

    subgraph Inventory["Inventory hand-off"]
        inv["hcloud.yml plugin<br/>or hcloud_inventory.yml.j2"]
    end

    play -->|"creates"| net
    play -->|"creates"| fip
    play -->|"creates"| proxy_group
    play -->|"creates"| vault_group
    play -->|"creates"| cp_group
    play -->|"creates"| wk_group
    play -->|"emits groups"| inv
```

---

## Inventory group contract

The role assigns servers to inventory groups based on the `role` label applied
at server creation time. Label *values* and group *names* are illustrative
examples — choose whatever names your downstream plays consume:

| Hetzner label | Inventory group (example) |
|---|---|
| `role=control-plane` | `server_nodes` |
| `role=worker` | `agent_nodes` |
| `role=proxy` | `proxy_hosts` |
| `role=vault` | `vault` |

The dynamic inventory plugin (`hcloud.yml`) uses a `groups:` map to produce
these names. The static template (`templates/hcloud_inventory.yml.j2`) uses
the same mapping. Either hand-off produces an inventory that downstream plays
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
9. Load balancers (optional, alternative to a self-hosted load balancer)
10. Outputs: set `hcloud_provisioned_servers` fact; render static inventory
