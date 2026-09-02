# Capability and Assurance

## Capability Gate

Record tri-state capabilities. `null` means unknown and must not be treated as success:

- repository access;
- shell access;
- Git access;
- write access;
- Python execution;
- project-test execution;
- browser access;
- GitHub or equivalent connector access.

`python_execution` only proves the controller scripts can run. `project_test_execution` becomes true only after the controller actually executes the frozen project verification commands successfully.

## Degraded Modes

- Without repository access, provide product and engineering artifacts but no repository facts.
- Without shell or Git, generate a coding-agent task and record an external blocker.
- Without project-test execution, do not close at `local_verified`.
- Without browser access, prepare manual scenarios but do not claim browser results.
- Without a connector, local scripts may verify commits and content, but remote CI remains externally attested rather than independently verified.

## Degraded capability: executable technical handoff

When the Controller lacks a capability required to establish a technical claim (repository, runtime, test, browser, Git, or comparable access):

- The Controller cannot fabricate technical completion, and unverified claims stay explicitly unverified.
- Technical judgment is not transferred to the Product Owner: the Product Owner is not asked to read code, logs, or test output to decide correctness.
- Prefer direct delegation or tool transfer to a capable role when that is available.
- When direct delegation is unavailable, produce a **minimum executable technical handoff** for a capable receiving role. A vague referral such as "find someone who can access the repository and take a look" is not an executable handoff.

The handoff must let the receiving capable role act without rediscovering context:

1. bounded objective / change identity;
2. relevant artifact/repository/runtime pointer;
3. frozen boundary/contract identity, when one exists;
4. exact requested action/verification;
5. expected returned evidence;
6. relevant stop conditions;
7. explicitly unverified facts.

Human Courier may carry the handoff package as a transfer action only; it is never the technical reviewer and never supplies the technical judgment.

## Closure Assurance

- `local_verified`: the controller verified repository identity, branch containment, reviewed-content equality, and actually executed every frozen post-merge command, storing exit codes and digested logs.
- `remote_verified`: remote PR/CI state was independently fetched with a connector and linked in the integration record.
- `externally_attested`: an identified human or system supplied the remote result; the controller did not independently fetch it.

A workflow closed at any assurance level is not automatically production-safe. Production authentication, permissions, tenant isolation, sensitive data, migrations, deployment, monitoring, recovery, and compliance still require qualified human review.
