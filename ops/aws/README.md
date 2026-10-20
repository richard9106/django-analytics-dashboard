# AWS migration foundation

`foundation.json` provisions a single Ubuntu 24.04 x86_64 `t3a.medium` in a dedicated
VPC, one public subnet, one final Elastic IP, a free S3 gateway endpoint, a 60 GiB
encrypted gp3 root disk, private versioned document and backup buckets, and daily
EBS snapshots (seven recovery points). EC2 uses standard CPU credits, basic
monitoring and IMDSv2 (hop limit 2 for Docker instance-role credentials).

No application secrets, data, DNS records, Stripe/SMTP credentials, or application
processes are installed. Bootstrap installs Docker/Compose, Nginx (HTTP 404 only),
unattended updates and encrypted-volume-backed swap. The `deploy` user receives
only the provided public SSH key. SSH is restricted to the operator IPv4 `/32`;
PostgreSQL and Gunicorn have no public firewall ports. No permanent AWS access keys
are created. The host role can access only these buckets, and cannot delete backup
objects or object versions. SSM provides an authenticated administration path.

## Validation and provisioning

Use temporary SSO credentials for the BAA-covered account. Validate before creating:

```sh
aws cloudformation validate-template --profile nuviamy --region us-east-1 \
  --template-body file://ops/aws/foundation.json
cfn-lint ops/aws/foundation.json
```

Create a CloudFormation change set with `CAPABILITY_IAM`, `OperatorCidr` (current
public IPv4 `/32`), and `OperatorPublicKey` (public Ed25519 key only). Inspect changes
before executing. Enable stack termination protection. Keep parameters, change-set
IDs, resource IDs, host fingerprints and deployment evidence in private operator
storage; never commit private keys or environment files.

## Cost and recovery boundaries

This starts billable resources, using the approximately $41.77/month calculator
baseline before taxes, logs, growth and any excess traffic. Credits and budget
alerts are not a spending cap. There may briefly be an automatically assigned IPv4
while the final Elastic IP is associated. No NAT, ALB, paid support subscription,
customer-managed KMS key or Reserved Instance/Savings Plan is created.

Snapshots keep seven daily recovery points (the calculator used a more conservative
30-point estimate). This infrastructure estimate is not a clinical retention policy.
The separate backup bucket expires `postgres/` backups and their noncurrent versions
after 35 days. Documents and their versions never expire automatically. Both buckets
remain on stack deletion/replacement. The host and its root disk are retained, so
stack deletion alone does NOT stop all costs. Do not delete clinical history to save
money. Bootstrap and recovery-point creation require operational verification.

## Migration gates

Follow `docs/compliance/migration-plan.md`. Preserve Django/Fernet decryption keys,
use distinct restored PostgreSQL roles, and first restore into a private isolated
rehearsal with external credentials and stored OAuth tokens disabled. Restrict
outbound networking during restoration; never let a rehearsal send mail, reminders,
Google exports, Stripe calls or backups to the source R2 bucket.

Before cutover, add IAM-role support to Compose/storage/backup runtime, implement
backup storage in the separate S3 bucket, configure TLS, validate restoration and
application/clinical digests, tune Gunicorn to the 4 GiB host, and migrate deploy
access and GitHub secrets deliberately. Only then freeze writes, take a fresh final
copy and switch DNS. Until that point Contabo/R2 remain the live environment and
are not covered by the AWS BAA. The BAA does not certify the application.

## Native S3 and isolated rehearsal

Set `DJANGO_STORAGE_BACKEND=s3`, `AWS_S3_REGION_NAME=us-east-1` and the documents
bucket. Empty static access key/secret/token and endpoint select the instance role.
Set `BACKUP_S3_BUCKET` to the separate backups bucket, `BACKUP_S3_PREFIX=postgres`.
The backup uploader preserves the legacy R2 destination when BACKUP_S3_BUCKET is
unset. GPG receives its passphrase on a private file descriptor, not a process argument.
On a new host, install boto3 for the host backup interpreter (bootstrap does this).

For restoration use a unique checkout, private prepared env, and Compose project:
`docker compose -p nuviamy-rehearsal --env-file rehearsal.env -f docker-compose.yml
-f ops/aws/rehearsal.compose.yml ...`. Build before restoring secrets/data. The
runtime Docker network is internal-only, EC2 credential lookup disabled, and web
uses isolated local media. Before starting web, restore the separate *_rehearsal
DB and run `isolate_rehearsal --confirm-isolated` to clear stored integration tokens.
Do not create reminder/backup timers on the rehearsal. Do not reuse its volume for
production or activate its copied subscription identifiers against Stripe.
