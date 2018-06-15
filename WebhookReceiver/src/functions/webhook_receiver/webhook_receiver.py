import base64
from hmac import compare_digest
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN', None)
USERNAME = os.getenv('USERNAME', None)
PASSWORD = os.getenv('PASSWORD', None)
WEBHOOK_TOPIC = os.getenv('WEBHOOK_TOPIC')


def response(message, status_code):
    """Returns a dictionary object for an API Gateway Lambda integration
    response.

    :param message: Message for JSON body of response
    :type message: str or dict

    :param int status_code: HTTP status code of response

    :rtype: dict
    """
    if isinstance(message, str):
        message = {'message': message}

    return {
        'isBase64Encoded': False,
        'statusCode': status_code,
        'body': json.dumps(message),
        'headers': {'Content-Type': 'application/json'}
    }


def authenticate(auth_header):
    if not auth_header:
        return False

    try:
        _, value = auth_header.split('Basic ')
        decoded = base64.b64decode(value).decode()
        username, password = decoded.split(':', 1)
    except:
        return False

    return compare_digest(username, USERNAME) and \
        compare_digest(password, PASSWORD)


def publish_event(event_data):
    sns_client = boto3.client('sns')

    try:
        resp = sns_client.publish(
            TopicArn=WEBHOOK_TOPIC,
            Message=json.dumps(event_data),
            MessageStructure='string'
        )
    except ClientError:
        logger.exception('Error sending SNS notification')
        raise


def lambda_handler(event, context):
    """Processes an inbound webhook from Jamf Pro and publishes to an SNS topic.

    If there is an ``ACCESS_TOKEN`` value present, inbound requests are required
    to have a ``?access_token=XXX`` query string parameter to authenticated to
    the processor.

    If there is no ``ACCESS_TOKEN`` requests can be unauthenticated.
    """
    logger.info(event)
    try:
        request_data = json.loads(event['body'])
    except (TypeError, json.JSONDecodeError):
        logger.exception('Bad Request: No JSON content found')
        return response('Bad Request: No JSON content found', 400)

    if ACCESS_TOKEN:
        logger.info('Token authentication required....')
        query_string_params = event['queryStringParameters'] or {}
        request_token = query_string_params.get('access_token', '')

        if not compare_digest(request_token, ACCESS_TOKEN):
            logger.error('Token not provided or does not match ACCESS_TOKEN')
            return response('Unauthorized', 401)

    if USERNAME and PASSWORD:
        logger.info('Basic Authentication required...')
        headers = event['headers']
        auth_header = headers.get('Authorization')

        if not authenticate(auth_header):
            logger.error('Bad username/password')
            return response('Unauthorized', 401)

    try:
        publish_event(request_data)
    except ClientError:
        return response('Internal Server Error', 500)

    return response('Success', 201)
