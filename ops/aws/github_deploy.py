"""Invoke the fixed deployment document with temporary GitHub OIDC credentials."""
import argparse
import re
import time

import boto3
from botocore.exceptions import ClientError


def deploy(instance, document, revision, mode):
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or mode not in {'Validate', 'Deploy'}:
        raise ValueError('A full reviewed SHA and valid deployment mode are required.')
    client = boto3.client('ssm')
    command = client.send_command(
        InstanceIds=[instance], DocumentName=document,
        Parameters={'Revision': [revision], 'Mode': [mode]},
        TimeoutSeconds=120, Comment=f'NuviaMy {mode} {revision}',
    )['Command']['CommandId']
    print(f'SSM command: {command}', flush=True)
    # Output is deliberately not copied into public GitHub logs: production errors
    # can contain sensitive configuration or record information.
    deadline = time.monotonic() + 3300
    while time.monotonic() < deadline:
        try:
            status = client.get_command_invocation(CommandId=command, InstanceId=instance)['Status']
        except ClientError as exc:
            if exc.response['Error']['Code'] != 'InvocationDoesNotExist':
                raise
            status = 'Pending'
        if status == 'Success':
            print(f'{mode} succeeded.', flush=True)
            return
        if status in {'Failed', 'Cancelled', 'TimedOut', 'Cancelling'}:
            raise RuntimeError(f'{mode} ended with {status}; inspect private SSM logs ({command}).')
        time.sleep(10)
    raise TimeoutError(f'SSM command still pending: {command}; inspect before retrying.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance', required=True)
    parser.add_argument('--document', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--mode', choices=['Validate', 'Deploy'], required=True)
    args = parser.parse_args()
    deploy(args.instance, args.document, args.revision, args.mode)
