# Security

Trailbun is a local CLI and a set of project-local hooks. It runs commands from
a contract you wrote, reads and writes `.trailbun/` inside your worktree, and
edits the hook configuration files that `setup` names. It makes no network
calls.

## What Trailbun is not

It is not a sandbox and not a security boundary. The agent has the same CLI
as you do, can amend or abandon the task, and can rewrite `.trailbun/` with any
shell command. Trailbun records these actions; it does not prevent them. The
[claims table](docs/EVIDENCE.md#claims) says which controls are enforced by a
host and which are only recorded.

## Reporting

Report a vulnerability through GitHub private vulnerability reporting on this
repository once it is enabled, or by opening an issue that omits the exploit
details and asks for a private channel. Please include the Trailbun version,
the host and its version, the operating system, and a reproduction.

Findings that count: a way to make a hook report a deny or a passing receipt
that did not happen; a way for the installed configuration to reach outside
the project; a redaction gap that leaks a credential shape the register lists
as covered. A shell write outside scope is a documented limit rather than a
vulnerability.

Only the latest release is supported.
