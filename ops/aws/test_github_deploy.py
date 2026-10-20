import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

from ops.aws.github_deploy import deploy


class DeploymentCommandTests(unittest.TestCase):
    @patch('ops.aws.github_deploy.boto3.client')
    def test_invalid_revision_is_rejected_before_accessing_aws(self, factory):
        with self.assertRaises(ValueError):
            deploy('instance', 'document', 'main; command', 'Deploy')
        factory.assert_not_called()

    @patch('ops.aws.github_deploy.time.sleep')
    @patch('ops.aws.github_deploy.boto3.client')
    def test_waits_for_eventually_consistent_invocation(self, factory, sleep):
        client = factory.return_value
        client.send_command.return_value = {'Command': {'CommandId': 'id'}}
        client.get_command_invocation.side_effect = [
            ClientError({'Error': {'Code': 'InvocationDoesNotExist'}}, 'GetCommandInvocation'),
            {'Status': 'InProgress'}, {'Status': 'Success'},
        ]
        deploy('instance', 'document', 'a' * 40, 'Validate')
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(client.send_command.call_args.kwargs['Parameters']['Mode'], ['Validate'])

    @patch('ops.aws.github_deploy.boto3.client')
    def test_failed_command_does_not_expose_production_output(self, factory):
        client = factory.return_value
        client.send_command.return_value = {'Command': {'CommandId': 'id'}}
        client.get_command_invocation.return_value = {'Status': 'Failed', 'StandardErrorContent': 'private data'}
        with self.assertRaises(RuntimeError) as failure:
            deploy('instance', 'document', 'a' * 40, 'Deploy')
        self.assertNotIn('private data', str(failure.exception))

    @patch('ops.aws.github_deploy.boto3.client')
    def test_permission_errors_are_not_silenced_as_pending(self, factory):
        client = factory.return_value
        client.send_command.return_value = {'Command': {'CommandId': 'id'}}
        client.get_command_invocation.side_effect = ClientError({'Error': {'Code': 'AccessDeniedException'}}, 'GetCommandInvocation')
        with self.assertRaises(ClientError):
            deploy('instance', 'document', 'a' * 40, 'Validate')
