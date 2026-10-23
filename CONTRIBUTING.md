# Contributing to ReorderWitness

Thanks for considering a contribution. ReorderWitness is a small experimental Python CLI for finding input-order-dependent results in JSONL processors. Its narrow scope is intentional.

## Before opening a change

- For a bug, open a [bug report](https://github.com/alkinbg/ReorderWitness/issues/new/choose) with a small, **synthetic** reproduction.
- For a new feature or a broad change, open an issue first to discuss the concrete use case and whether it fits the project's scope.
- Security vulnerabilities belong in [private vulnerability reports](SECURITY.md), not public issues.
- Please follow our [code of conduct](CODE_OF_CONDUCT.md).

## Local setup

Python 3.11 or newer is required. The CLI has no third-party runtime dependencies.

```bash
git clone https://github.com/alkinbg/ReorderWitness.git
cd ReorderWitness
python -m venv .venv
# Activate the virtual environment using the command appropriate for your shell.
python -m pip install -e .
python -m unittest discover -s tests -v
```

The CI currently runs on Ubuntu with Python 3.11, 3.12 and 3.13. Local checks on additional platforms are welcome, but do not claim compatibility without testing.

## Changes and tests

- Keep changes focused and preserve the existing stdin/stdout JSONL and CLI exit-code contracts unless a breaking change is explicitly discussed.
- Add regression tests for bug fixes. Test confirmed differences, correct/inconclusive behavior, and execution-budget handling when relevant.
- Use standard-library Python where practical and type annotations for new public code.
- Do not run experimental targets against production systems. Test fixtures must be deterministic, isolated and free of real credentials, private records, or side effects.
- Run `python -m unittest discover -s tests -v` and check `git diff --check` before opening a pull request.
- Describe what changed, why it matters, and how it was verified; use the [PR template](.github/PULL_REQUEST_TEMPLATE.md).

No requirement to run arbitrary code supplied in issue reports is implied. Maintainers review contributions as time allows; submission does not guarantee merge. Contributions accepted into this repository are distributed under the project's [MIT License](LICENSE).
