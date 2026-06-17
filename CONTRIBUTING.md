# CONTRIBUTING

## Why Read This?

Following these guidelines ensures your time and ours is well respected. Clear, thoughtful contributions improve response time, reduce confusion, and increase the likelihood of your changes being merged.

## What You Can Contribute

We welcome contributions of all kinds:

* Code (new features or bug fixes)
* Bug reports or feature requests
* Documentation improvements
* Molecule scenario improvements or new test scenarios

## What We Are Not Looking For

Please avoid:

* Feature suggestions that lack context or a use case
* Support questions (use Discussions or Stack Overflow instead)
* Unreviewed PRs touching core design without prior discussion

If unsure, open a GitHub Issue to discuss first.

## Code of Conduct

Please review our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to fostering a safe, inclusive environment for everyone.

## Getting Started

1. Fork the repo and clone it locally
2. Create a branch: `git checkout -b feature/your-feature`
3. Install dependencies: `pip install -r requirements.txt`
4. Install the collection: `ansible-galaxy collection install -r requirements.yml`
5. Run linting: `ansible-lint --profile production && yamllint .`
6. Run offline tests: `molecule test -s default`
7. Push your branch and open a PR

If your change is non-trivial, open an issue first so we can discuss approach.

## Obvious Fix Policy

You do not need to open an issue for:

* Fixing typos or formatting
* Comment updates
* Minor README changes
* `.gitignore` tweaks

## Standards

* FQCN for all modules (`ansible.builtin.copy`, `hetzner.hcloud.server`, etc.)
* `ansible-lint --profile production` must pass with zero failures
* `yamllint .` must pass clean
* `molecule test -s default` must pass with no HCLOUD_TOKEN set
* Any new variable must have a matching entry in `meta/argument_specs.yml` and a comment in `defaults/main.yml`
* No secrets, tokens, or hardcoded credentials in any committed file
* No `command`/`shell` tasks without `changed_when`/`creates` guards

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) style:

```
feat(networks): add support for vswitch subnet type
fix(validate): correct teardown guard filter expression
docs(readme): add dynamic inventory example
```

## Contact

**Email:** info@devopsgroup.sk
