# System-Python study gate

This batch uses the same system-backed Python 3.12.10 environment for each cell,
separate from the earlier user-profile Python batches. Windows sandbox setup is
selected with the documented process-only `windows.sandbox="elevated"` option.
The runtime is externally bootstrapped under `.trailbun` before the model starts.

In the first plain scope cell, the prescribed interpreter ran acceptance
successfully. The independent grader also passed functional acceptance. The
model created an additional `DIAGNOSIS.md`, outside this task's allowed artifact
set, so the predefined overall task score is false. This is recorded as an
observed artifact difference, not a general claim about ordinary agents.

The parent could read the changed application files but received `PermissionError`
when exporting the newly created diagnosis file. Its actual content was not
independently copied. The tracked patch, original fixture and full sanitized host
events remain available. The exporter was subsequently fixed to record each
unreadable file's omission while preserving the rest of future bundles.

The first cell has an explicitly labeled source hash observation taken after the
run; no before snapshot exists. Future cells capture before/after module hashes.
Do not infer source stability for the first cell from a later observation.

Missing cells are not successes. A guarded diagnostic counterpart may establish
whether sandbox-created runtime state is accessible across the model and parent;
it does not establish product efficacy or native hook enforcement.

A later review also found that Codex automatically persisted this temporary
project's trust in user configuration. No before/after configuration hash exists
for this cell. Later runners supply explicit process trust and record hashes.
The unreadable-file behavior is consistent with the owner-relative ACL that
Python's TemporaryDirectory creates on Windows; it is not evidence that every
ordinary Windows repository has this access problem.
