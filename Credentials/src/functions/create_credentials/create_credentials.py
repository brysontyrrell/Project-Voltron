import json
import logging
import os

import boto3
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

STACK_NAME = os.getenv('STACK_NAME')
USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')


def send_cf_response(event, context, success=True, reason='Unknown'):
    data = {
        'Status': 'SUCCESS' if success else 'FAILED',
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId']
    }
    if not success:
        data['Reason'] = reason

    headers = {
        'Content-Type': ''
    }

    logger.info(f"Sending CloudFormation response to {event['ResponseURL']}")
    resp = requests.put(
        event['ResponseURL'],
        data=json.dumps(data),
        headers=headers
    )
    logger.info(resp.status_code)


def create(client):
    client.put_parameter(
        Name=f'/voltron/{STACK_NAME}/username',
        Description='Jamf Pro Username',
        Value=USERNAME,
        Type='String',
        Overwrite=True
    )

    client.put_parameter(
        Name=f'/voltron/{STACK_NAME}/password',
        Description='Jamf Pro Password',
        Value=PASSWORD,
        Type='SecureString',
        Overwrite=True
    )


def delete(client):
    client.delete_parameters(
        Names=[
            f'/voltron/{STACK_NAME}/username',
            f'/voltron/{STACK_NAME}/password'
        ]
    )


def lambda_handler(event, context):
    logger.info(event)
    client = boto3.client('ssm')

    if event['RequestType'] == 'Create':
        action = create
    elif event['RequestType'] == 'Delete':
        action = delete
    else:
        send_cf_response(event, context, reason='Unsupported Event')
        return {}

    try:
        action(client)
    except Exception as err:
        logger.exception('Unable to write to Parameter Store')
        send_cf_response(event, context, False, str(err))

    send_cf_response(event, context)
    return {}
