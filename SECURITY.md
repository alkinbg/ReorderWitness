# Security Policy

## Supported versions

ReorderWitness is an **experimental, pre-release project**. Only the current `main` branch is considered for security fixes on a best-effort basis. There are no stable release branches or guaranteed support windows.

## Report a vulnerability privately

**Please do not open a public issue containing an exploitable security vulnerability, credentials, or sensitive data.**

Use [GitHub Security Advisories](https://github.com/alkinbg/ReorderWitness/security/advisories) and select **Report a vulnerability**. Private vulnerability reporting is enabled for this repository.

Include the affected commit or version, relevant environment, a minimal reproduction with **synthetic data**, the expected versus observed behavior, and a description of the security impact. The maintainer will review reports as availability permits; no specific response or fix deadline is promised.

Use public [GitHub issues](https://github.com/alkinbg/ReorderWitness/issues) for ordinary non-security bugs or documentation problems.

## Security boundaries

ReorderWitness repeatedly executes the command supplied after `--`. It is **not a sandbox**: child processes inherit the caller's effective permissions and environment, and may access files or the network. The built-in time and captured-output budgets are **not memory/CPU isolation** or a guarantee that all subprocess descendants are terminated.

Only test trusted, deterministic, side-effect-free commands using synthetic or disposable data. Never run it on production workloads or untrusted downloaded executables without independent isolation configured by you. Evidence files can contain input and output records; handle them accordingly.
