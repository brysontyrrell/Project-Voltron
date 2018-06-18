import json
import logging
import os

import boto3
from botocore.exceptions import ClientError
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not (os.getenv('JSS_USERNAME') and os.getenv('JSS_PASSWORD')):
    raise Exception('Jamf Pro credentials are required for Poller operation')

POLLER_TOPIC = os.getenv('POLLER_TOPIC')
URL = 'https://' + os.path.join(
    os.getenv('JSS_DOMAIN'),
    'JSSResource',
    os.getenv('JSS_ENDPOINT'),
    'id',
    os.getenv('JSS_OBJECT_ID')
)


def poll_jamf_pro():
    try:
        resp = requests.get(
            URL,
            headers={'Accept': 'application/json'},
            auth=(os.getenv('JSS_USERNAME'), os.getenv('JSS_PASSWORD')),
            timeout=90
        )
        resp.raise_for_status()
    except requests.ConnectionError:
        logger.exception('Unable to connect to Jamf Pro API')
        raise
    except requests.HTTPError:
        logger.exception('Error communicating with Jamf Pro API')
        raise

    logger.info(f'API request successful: {resp.status_code}')
    return resp.json()


def publish_data(data):
    sns_client = boto3.client('sns')

    try:
        resp = sns_client.publish(
            TopicArn=POLLER_TOPIC,
            Message=json.dumps(data),
            MessageStructure='string'
        )
    except ClientError:
        logger.exception('Error sending SNS notification')
        raise


def lambda_handler(event, context):
    logger.info(f'Requesting data for: {URL}')
    api_data = poll_jamf_pro()

    logger.info('Publishing response to SNS topic...')
    publish_data(api_data)

    return 'Success'
