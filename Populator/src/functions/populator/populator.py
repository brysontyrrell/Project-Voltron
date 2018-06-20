import json
import logging
import os
from xml.etree import ElementTree as ET

import boto3
from botocore.exceptions import ClientError
from botocore.vendored import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

if not (os.getenv('JSS_USERNAME') and os.getenv('JSS_PASSWORD')):
    raise Exception('Jamf Pro credentials are required for Populator operation')

BUCKET_NAME = os.getenv('BUCKET_NAME')
SOURCE_FILE = os.getenv('SOURCE_FILE')

URL = 'https://' + os.path.join(
    os.getenv('JSS_DOMAIN'),
    'JSSResource',
    os.getenv('DEVICE_TYPE').lower(),
    'serialnumber'
)

XML_ROOT = os.getenv('XML_ROOT')
XML_KEY_MAP = {
    'barcode_1': 'general/barcode_1',
    'barcode_2': 'general/barcode_2',
    'asset_tag': 'general/asset_tag',
    'site_id': 'general/site/id',
    'site_name': 'general/site/name',
    'username': 'location/username',
    'real_name': 'location/real_name',
    'email_address': 'location/email_address',
    'position': 'location/position',
    'phone_number': 'location/phone_number',
    'department': 'location/department',
    'building': 'location/building',
    'room': 'location/room',
    'is_purchased': 'purchasing/is_purchased',  # bool
    'is_leased': 'purchasing/is_leased',  # bool
    'po_number': 'purchasing/',
    'vendor': 'purchasing/vendor',
    'applecare_id': 'purchasing/applecare_id',
    'purchase_price': 'purchasing/purchase_price',
    'purchasing_account': 'purchasing/purchasing_account',
    'po_date': 'purchasing/po_date',  # date string
    'purchasing_contact': 'purchasing/purchasing_contact'
}


def is_valid_event(webhook):
    if not webhook or not webhook.get('webhookEvent'):
        return False

    if webhook['webhookEvent'] in ('ComputerAdded', 'MobileDeviceEnrolled'):
        return True
    else:
        return False


def query_s3(serial_number):
    client = boto3.client('s3')

    try:
        resp = client.select_object_content(
            Bucket=BUCKET_NAME,
            Key=SOURCE_FILE,
            ExpressionType='SQL',
            Expression="SELECT * FROM S3Object s WHERE "
                       f"s.serial_number = '{serial_number}'",
            InputSerialization={
                'CompressionType': 'NONE',
                'CSV': {
                    'FileHeaderInfo': 'USE',
                    'RecordDelimiter': '\n',
                    'FieldDelimiter': ','
                }
            },
            OutputSerialization={
                'JSON': {}
            }
        )
    except ClientError:
        logger.exception('Unable to query data source in S3')
        raise

    for i in resp['Payload']:
        if i.get('Records'):
            return json.loads(i['Records']['Payload'].decode())

    return None


def generate_xml(data):
    xml_root = ET.Element(XML_ROOT)

    general = ET.SubElement(xml_root, 'general')
    location = ET.SubElement(xml_root, 'location')
    purchasing = ET.SubElement(xml_root, 'purchasing')

    for key, value in data.items():
        if key in XML_KEY_MAP.keys():
            element, path = XML_KEY_MAP[key].split('/')
            if element == 'general':
                ET.SubElement(general, path).text = str(value)
            elif element == 'location':
                ET.SubElement(location, path).text = str(value)
            elif element == 'purchasing':
                ET.SubElement(purchasing, path).text = str(value)

    if not general:
        xml_root.remove(general)
    if not location:
        xml_root.remove(location)
    if not purchasing:
        xml_root.remove(purchasing)

    return ET.tostring(xml_root).decode()


def update_jamf_pro_record(data):
    xml = generate_xml(data)

    try:
        resp = requests.put(
            os.path.join(URL, data['serial_number']),
            headers={'Content-Type': 'text/xml'},
            data=xml,
            auth=(os.getenv('JSS_USERNAME'), os.getenv('JSS_PASSWORD')),
            timeout=30
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


def lambda_handler(event, context):
    """Order of operations:

    1) Process event (must be ComputerAdded or MobileDeviceEnrolled)
    2) Query S3 file using serial number
    3) Perform update on record in Jamf Pro
    """
    if event.get('Records'):
        logging.info('Processing SNS records...')
        for record in event['Records']:
            try:
                event_data = json.loads(record['Sns']['Message'])
            except (TypeError, json.JSONDecodeError):
                logger.exception('Bad Request: No JSON content found')
                return {}

            webhook_event = event_data.get('event')
            webhook_data = event_data.get('webhook')

            if not webhook_event and webhook_data:
                logger.error('Invalid data passed by SNS notification')
                return {}

            if not is_valid_event(event):
                logger.info('The webhook event is not supported.')
                return {}

            serial_number = webhook_event.get('serialNumber')
            if not serial_number:
                logger.error('A device serial number was not found')
                return {}

            s3_record = query_s3(serial_number)
            if not s3_record:
                logger.info(f'The serial {serial_number} number was not found '
                            'in the data source')
                return {}

            update_jamf_pro_record(s3_record)

    return {}
