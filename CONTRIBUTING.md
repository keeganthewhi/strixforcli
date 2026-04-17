# Contributing

> You're looking at `strixnoapi`, a fork of
> [`usestrix/strix`](https://github.com/usestrix/strix). Contributions to
> the core scan engine go upstream; contributions to the subscription
> proxy, hardening layer, setup/doctor/audit subcommands, or report
> exporters land here.

## Contributing to strixnoapi specifically

### Golden rule

**Never modify `strix/`.** That directory is upstream code, vendored
verbatim. Changes there break our cherry-pick workflow.
All strixnoapi additions go under `strixnoapi/`.

### Quickstart

```bash
git clone https://github.com/keeganthewhi/strixnoapi.git
cd strixnoapi
uv sync
make verify                       # ruff + pytest on strixnoapi/
uv run strix setup --auto         # authenticate
uv run strix doctor               # confirm env is healthy
```

### What to work on

- **proxy/** — translators for new CLIs, auth improvements, rate-limit
  policies, injection-guard patterns.
- **interface/** — new subcommands, TUI polish, help text.
- **security/** — sandbox profile refinements, new secret patterns,
  SBOM format upgrades.
- **runtime/** — platform-compat shims for dependencies that misbehave
  (like the Windows Docker npipe patch).
- **docs/** — anything that makes the first-run experience faster.

### Syncing with upstream

```bash
git remote add upstream https://github.com/usestrix/strix.git   # once
uv run strix update --dry-run                                   # preview
git merge upstream/main                                         # apply
uv run pytest                                                   # regression
```

### PR checklist

- [ ] `uv run ruff check strixnoapi/` → zero errors
- [ ] `uv run pytest tests/strixnoapi/ --no-cov` → all green
- [ ] No touches to `strix/`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] Conventional Commits format
- [ ] No `console.log`, no debug `print` in production paths
- [ ] No secrets, tokens, or identifiers in diffs or tests

### Issue templates

- **Bug**: proxy translator mis-translation, sandbox hardening
  regression, UX surprise in setup/doctor/audit.
- **Enhancement**: new CLI support (Codex → future backends), new
  report formats, seccomp tightening.
- **Upstream bridge**: strix core behaviour that would ease the
  subscription-OAuth integration if changed upstream.

---

## Contributing to upstream Strix (historical)

Below is the upstream project's contributor guide — relevant if your
change belongs in the scan engine itself rather than in strixnoapi.

---

# Contributing to Strix

Thank you for your interest in contributing to Strix! This guide will help you get started with development and contributions.

## 🚀 Development Setup

### Prerequisites

- Python 3.12+
- Docker (running)
- [uv](https://docs.astral.sh/uv/) (for dependency management)
- Git

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/usestrix/strix.git
   cd strix
   ```

2. **Install development dependencies**
   ```bash
   make setup-dev

   # or manually:
   uv sync
   uv run pre-commit install
   ```

3. **Configure your LLM provider**
   ```bash
   export STRIX_LLM="openai/gpt-5.4"
   export LLM_API_KEY="your-api-key"
   ```

4. **Run Strix in development mode**
   ```bash
   uv run strix --target https://example.com
   ```

## 📚 Contributing Skills

Skills are specialized knowledge packages that enhance agent capabilities. See [strix/skills/README.md](strix/skills/README.md) for detailed guidelines.

### Quick Guide

1. **Choose the right category** (`/vulnerabilities`, `/frameworks`, `/technologies`, etc.)
2. **Create a** `.md` file with your skill content
3. **Include practical examples** - Working payloads, commands, or test cases
4. **Provide validation methods** - How to confirm findings and avoid false positives
5. **Submit via PR** with clear description

## 🔧 Contributing Code

### Pull Request Process

1. **Create an issue first** - Describe the problem or feature
2. **Fork and branch** - Work from the `main` branch
3. **Make your changes** - Follow existing code style
4. **Write/update tests** - Ensure coverage for new features
5. **Run quality checks** - `make check-all` should pass
6. **Submit PR** - Link to issue and provide context

### PR Guidelines

- **Clear description** - Explain what and why
- **Small, focused changes** - One feature/fix per PR
- **Include examples** - Show before/after behavior
- **Update documentation** - If adding features
- **Pass all checks** - Tests, linting, type checking

### Code Style

- Follow PEP 8 with 100-character line limit
- Use type hints for all functions
- Write docstrings for public methods
- Keep functions focused and small
- Use meaningful variable names

## 🐛 Reporting Issues

When reporting bugs, please include:

- Python version and OS
- Strix version
- LLMs being used
- Full error traceback
- Steps to reproduce
- Expected vs actual behavior

## 💡 Feature Requests

We welcome feature ideas! Please:

- Check existing issues first
- Describe the use case clearly
- Explain why it would benefit users
- Consider implementation approach
- Be open to discussion

## 🤝 Community

- **Discord**: [Join our community](https://discord.gg/strix-ai)
- **Issues**: [GitHub Issues](https://github.com/usestrix/strix/issues)

## ✨ Recognition

We value all contributions! Contributors will be:
- Listed in release notes
- Thanked in our Discord
- Added to contributors list (coming soon)

---

**Questions?** Reach out on [Discord](https://discord.gg/strix-ai) or create an issue. We're here to help!
