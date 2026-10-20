# AWS foundation verification — 20 October 2026

## Scope

The owner authorized one AWS destination based on the approximately USD 41.77/month
calculator estimate before tax, usage growth and other variable charges. AWS BAA
activation was confirmed by the owner for this account. A recurring USD 80 budget
exists; notifications do not enforce a hard spending cap. Contabo and R2 remain live.

## Delivered and verified

- CloudFormation foundation (PR 63) and bootstrap correction (PR 64); both attached
  to the task. Source on main: bc3ad6534e97b68bfa35b3336854f8279106a1e4.
- CloudFormation native validation, cfn-lint 1.57.2 and bootstrap shell syntax pass.
- One Ubuntu 24.04 t3a.medium with 60 GiB encrypted gp3 root volume, standard CPU
  credits, basic monitoring, IMDSv2 required and hop limit 2 for containers.
- Dedicated VPC/subnet, S3 gateway endpoint, one final Elastic IP. No NAT/ALB or
  customer-managed KMS key. SSH only from the operator /32; database ports closed.
- Dedicated operator SSH key held locally; only its public key uploaded. Host key
  obtained through authenticated SSM before enforcing strict SSH host checking.
- Docker Compose, Nginx HTTP-404 placeholder, updates and 2 GiB swap available.
- Separate S3 documents/backups buckets: all public access blocked, ownership
  enforced, AES256 default encryption, versioning, deny non-TLS requests.
- Document versions have no lifecycle deletion. Backup lifecycle applies current
  expiration at 35 days; noncurrent expiry is measured from becoming noncurrent,
  so this is not a strict 35-day total storage cap or a clinical retention policy.
- Daily DLM encrypted-instance snapshot policy enabled, seven recovery points.
  Scheduled policy verified; no claim that a full application restore has occurred.
- Root MFA enabled; no root access keys. Stack termination protection enabled.

## Actual smoke tests

1. Initial cloud-init stopped because /run/sshd did not exist before SSH validation.
   Original logs were preserved. Corrected bootstrap creates it, uses reload-or-restart,
   and guards swap initialization. Recovery and a second run both succeeded.
2. After CloudFormation update/restart, same instance and Elastic IP remained; Docker,
   Nginx, SSH restrictions and swap were operational. Deployed template matched Git.
3. Host used instance-role credentials (no permanent AWS keys) to put two fictional
   object versions and recover the older version; current version and server-side
   encryption checked. Role denied DeleteObjectVersion and backup DeleteObject.
4. Privileged operator removed only the fictional probe versions. Absence was checked
   in both buckets. No source customer records or files were copied or deleted.
5. Public production health returned OK; DNS still resolved to the original server.

Detailed resource IDs, template hash, operator parameters and verification evidence
are stored outside Git in the private local operator directory. No private keys,
production environment files, credentials or BAA terms are included in this report.

## Before production migration

- Add explicit S3/instance-role support to app configuration and Compose; current
  backend flag is named r2 and backup script expects static credentials/endpoint.
- Separate backup bucket integration; remove secrets from command arguments; verify
  scheduled DB backup, restoration and alerting before relying on it.
- Restore fresh encrypted copies into a private isolated rehearsal. Preserve Fernet
  and Django keys, separate DB credentials, disable external credentials and stored
  OAuth tokens before starting web/jobs, and block external service egress.
- Tune application workers for 4 GiB; install TLS; check permissions, record counts,
  signatures/addenda, private files, UI, Stripe/SMTP and source/destination isolation.
- Review remaining subprocessor/clinical-readiness gates. AWS BAA is not application
  certification and does not cover the current Contabo/R2 environment.
- Move GitHub deployment secrets/jobs and DNS only after rehearsal passes, with a
  fresh consistent final copy, one writer, and an explicit rollback procedure.
