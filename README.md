# Done Is Not Proof

> Output is not evidence. A rule is not a control. A hook that ran did not necessarily block anything.

**Done Is Not Proof** is an evidence-first field manual and toolkit for teams that use AI coding agents. It helps you distinguish what is claimed, what is enforced, and what has actually been measured.

## Start here

Audit Claude Code hook scripts for the most common fail-open mistake:

```bash
python checks/hook_exit_audit.py ~/.claude/hooks
```

The audit is intentionally narrow. It identifies explicit `exit 1` and `exit 2` statements in shell hook scripts; it does not prove complete hook coverage or runtime behavior.

Then run the 15-minute [Reality Check](playbook/REALITY_CHECK.md) and record evidence with a [Receipt Card](templates/RECEIPT.md).

## Three statuses

- `ASSERTED`: documented or claimed, but not demonstrated.
- `ENFORCED`: a mechanism can deterministically block or constrain the action.
- `MEASURED`: observed with a reproducible procedure and retained evidence.

A claim may have more than one status. Never promote a claim without attaching the receipt.

## The run contract

```text
CONTRACT -> BOUNDARY -> BUDGET -> CHECK -> RECEIPT
```

1. Define the intended outcome, exclusions, acceptance criteria, and stop conditions.
2. Bound files, tools, permissions, data, and side effects.
3. Cap time, retries, context, and change size.
4. Run deterministic checks against the produced artifact.
5. Preserve commands, outputs, versions, and unresolved limitations.

## Repository map

- `field-manual/`: durable laws and doctrine.
- `playbook/`: procedures you can run.
- `templates/`: copyable operating artifacts.
- `checks/`: executable, deliberately narrow checks.
- `tests/`: deterministic tests for executable claims.

## Current maturity

This repository begins as a public preview. The hook audit is tested as a text classifier. It is not yet evidence that a particular Claude Code installation is correctly configured or that every write path is blocked. Those stronger claims remain `ASSERTED` until fixtures and reference runs are published.

## Position

This project is pro-agent and anti-unearned autonomy. More autonomy is justified by better boundaries, receipts, and recovery—not by confidence, fluency, or a successful demo.

## Contributing

The most valuable contribution promotes one claim from `ASSERTED` to `MEASURED` or `ENFORCED` with a reproducible receipt. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
