# Troubleshooting

Common issues and how to resolve them.

---

## Table of Contents

- [Token / auth errors](#token--auth-errors)
- [Rate limits](#rate-limits)
- [Idempotency issues](#idempotency-issues)
- [Teardown safety errors](#teardown-safety-errors)
- [Offline testing with molecule](#offline-testing-with-molecule)
- [Useful commands reference](#useful-commands-reference)

---

## Token / auth errors

### `hcloud_api_token is empty`

**Symptom:** The role aborts with:
```
ASSERT FAILED: hcloud_api_token is empty. Export HCLOUD_TOKEN or inject from Vault.
```

**Cause:** `hcloud_provision: true` but no token was provided.

**Fix:** Export the token before running, or pass it via HashiCorp Vault / Ansible Vault:

```bash
# Option 1: environment variable
export HCLOUD_TOKEN="your-api-token"
ansible-playbook site.yml

# Option 2: Ansible extra-vars (only for testing, not recommended for production)
ansible-playbook site.yml -e hcloud_api_token="your-api-token"
```

For production, use a lookup at consume time:
```yaml
hcloud_api_token: "{{ lookup('community.hashi_vault.vault_kv2_get', 'hetzner/token').secret.value }}"
```

### `401 Unauthorized` from Hetzner API

**Symptom:** Module fails with an authentication error even though `HCLOUD_TOKEN` is set.

**Causes:**

| Error | Cause | Fix |
|---|---|---|
| Token has been deleted or rotated | Old token in environment | Generate a new token in Hetzner Cloud console under Security > API Tokens |
| Token has insufficient permissions | Read-only token used | Create a Read & Write token |
| Wrong project token | Token belongs to a different Hetzner project | Verify you are using the token for the correct project |

### `check_mode` unexpectedly hits the API

**Cause:** `hetzner.hcloud.*` modules query the live API even under `--check` to compute diffs. This is a known limitation of the collection.

**Fix:** For offline runs, use `hcloud_provision: false` instead of `--check`:
```bash
ansible-playbook site.yml -e hcloud_provision=false
```

The offline molecule scenario (`molecule test -s default`) uses this approach and requires no token.

---

## Rate limits

**Symptom:** Tasks fail intermittently with `429 Too Many Requests`.

**Cause:** Hetzner Cloud API limits requests per second per project. Creating many resources in quick succession (e.g. 10+ servers in one play) can hit the limit.

**Fix:**

- The `hetzner.hcloud` collection handles most rate limit retries transparently.
- If you are creating large numbers of resources, introduce delays using `loop_control.pause`:

```yaml
# In your custom task (not this role's internals)
loop_control:
  pause: 1   # seconds between iterations
```

- For very large infrastructure, provision resources in batches across multiple plays.

---

## Idempotency issues

### Server already exists with different attributes

**Symptom:** Attempting to change `server_type`, `image`, or `location` on an existing server causes a module error.

**Cause:** These attributes are immutable after server creation. The `hcloud.server` module does not silently recreate servers when immutable attributes change.

**Fix:**

- To resize: use `force: true` or `force_upgrade: true` (requires a server power-off).
- To rebuild with a new image: set `state: rebuild` in the task (advanced use case).
- To change location: destroy and recreate (set `state: absent` then `state: present`).

### SSH keys not appearing on an existing server

**Cause:** `ssh_keys` is a creation-time-only attribute. Adding or removing keys from the list has no effect on a running server.

**Fix:** Manage SSH keys at the OS level (`authorized_keys`) for existing servers.

### Firewall rules reordering

**Symptom:** The task reports `changed` every run even though rules look the same.

**Cause:** The Hetzner API may return rules in a different order. The `firewall` module compares the full list declaratively.

**Fix:** This is typically harmless (idempotent effect, just reports changed). If it is disruptive, ensure your rule order in `hcloud_firewalls[].rules` matches the canonical order returned by the API.

---

## Teardown safety errors

### `A resource is set to state=absent but hcloud_allow_teardown is false`

**Symptom:** The role aborts during `validate.yml` with this message.

**Cause:** `hcloud_allow_teardown: false` (the default) prevents any accidental destruction.

**Fix:** Always pass teardown permission explicitly on the CLI — never set it to `true` in a vars file committed to the repo:

```bash
ansible-playbook teardown.yml \
  -e hcloud_allow_teardown=true \
  --tags servers,server_networks   # scope to specific resources
```

### Resources not deleted after teardown

**Symptom:** Resources still appear in the Hetzner Cloud console after running with `state: absent`.

**Cause:** Dependency order — the API refuses to delete a network that still has servers attached, or a server that has volumes attached.

**Fix:** Follow the reverse dependency order for teardown:
1. `server_networks` (detach before deleting servers)
2. `servers`
3. `floating_ips`, `primary_ips`, `volumes`
4. `subnetworks`
5. `networks`
6. `firewalls`, `placement_groups`, `ssh_keys`

The `examples/teardown.yml` demonstrates the correct ordering.

---

## Offline testing with molecule

### `molecule test -s default` works without HCLOUD_TOKEN

The `default` molecule scenario is deliberately offline-safe. It sets `hcloud_provision: false`, which stops the role before any `hetzner.hcloud.*` module is invoked. No token is needed.

Do not attempt to use `--check` mode as an offline substitute — the collection still authenticates and queries the live API even under `--check`.

### `molecule test -s live` requires a real token

The `live` scenario creates actual Hetzner Cloud resources. It is not part of the default CI pipeline. To run it:

```bash
export HCLOUD_TOKEN="your-throwaway-project-token"
molecule test -s live   # always destroys resources at the end
```

Use a dedicated throwaway Hetzner project for this. Resources are automatically destroyed at the end of `molecule test` even if verify fails.

### `MOLECULE_IMAGE` variable

The `default` scenario uses `geerlingguy/docker-debian12-ansible:latest` by default. To test on a different distro:

```bash
MOLECULE_IMAGE="geerlingguy/docker-ubuntu2404-ansible:latest" molecule test -s default
```

---

## Useful commands reference

```bash
# Offline validate + lint (no token needed)
export PATH="$HOME/.venvs/ansible-roles/bin:$PATH"
yamllint .
ansible-lint --profile production .
ansible-playbook --syntax-check molecule/default/converge.yml

# Offline molecule (no token needed)
molecule test -s default

# Live molecule (token required, creates billable resources)
export HCLOUD_TOKEN="your-token"
molecule test -s live

# Validate YAML parses correctly (CI test)
python3 -c "import yaml; yaml.safe_load(open('.gitlab-ci.yml'))"
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# Count argument_specs entries vs defaults entries
grep -c '^\s\{6\}hcloud_' meta/argument_specs.yml
grep -c '^hcloud_' defaults/main.yml

# Teardown (scoped to servers only)
ansible-playbook examples/teardown.yml \
  -e hcloud_allow_teardown=true \
  --tags servers,server_networks
```
