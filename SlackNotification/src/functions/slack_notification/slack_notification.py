"""Create formatted Slack messages from Jamf Pro webhooks."""
import json
import logging
import os
import time

import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
IGNORED_EVENTS = os.getenv('IGNORED_EVENTS').split(',')


def _computer_added(data):
    """Return a formatted Slack message for the 'ComputerAdded' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A new computer has been added!\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Computer Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Computer Added',
        color='green',
        image='images/computers_64.png'
    )


def _computer_checkin(data):
    """Return a formatted Slack message for the 'ComputerCheckIn' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A computer check-in has occurred.\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Computer Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Computer Check-In',
        color='gray',
        image='images/computers_64.png'
    )


def _computer_inventory(data):
    """Return a formatted Slack message for the 'ComputerInventoryCompleted'
    event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A computer has submitted inventory.\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Computer Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Computer Inventory Complete',
        color='gray',
        image='images/computers_64.png'
    )


def _jss_shutdown(data):
    """Return a formatted Slack message for the 'JSSShutdown' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    text = 'The Jamf Pro web app *{}* has initiated a shutdown.'.format(
        data['jssUrl'])

    if data['isClusterMaster']:
        text += ' *(master)*'

    return _message(text, 'Jamf Pro Shutdown',
                    color='red', image='images/jss_64.png')


def _jss_startup(data):
    """Return a formatted Slack message for the 'JSSStartup' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    text = 'The Jamf Pro web app *{}* has started up.'.format(data['jssUrl'])

    if data['isClusterMaster']:
        text += ' *(master)*'

    return _message(text, 'Jamf Pro Startup',
                    color='green', image='images/jss_64.png')


def _mobile_checkin(data):
    """Return a formatted Slack message for the 'MobileDeviceCheckIn' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A mobile device check-in has occurred.\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Device Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Mobile Device Check-In',
        color='gray',
        image='images/mobiledevices_64.png'
    )


def _mobile_enrolled(data):
    """Return a formatted Slack message for the 'MobileDeviceEnrolled' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A mobile device been enrolled!\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Device Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Mobile Device Enrolled',
        color='green',
        image='images/mobiledevices_64.png'
    )


def _mobile_unenrolled(data):
    """Return a formatted Slack message for the 'MobileDeviceUnEnrolled' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'A mobile device been un-enrolled!\n'
        '*ID:* {} | *Serial Number:* {}\n'
        '*Device Name:* {} | *User:* {}'.format(
            data['jssID'], data['serialNumber'],
            data['deviceName'], data['username']
        ),
        'Mobile Device Un-Enrolled',
        color='yellow',
        image='images/mobiledevices_64.png'
    )


def _patch_title_updated(data):
    """Return a formatted Slack message for the 'PatchSoftwareTitleUpdated'
    event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    return _message(
        'Jamf Pro has received a new patch definition update.\n'
        '<{}|Click here to view the report>\n'
        '*Software Title:* {} | *New Version:* {}'.format(
            data['reportUrl'], data['name'], data['latestVersion']
        ),
        'Patch Definition Update',
        color='yellow',
        image='images/patch_64.png'
    )


def _rest_api_operation(data):
    """Return a formatted Slack message for the 'RestAPIOperation' event.

    :param dict data: The ``event`` data from a Jamf Pro webhook.

    :returns: Formatted Slack message.
    :rtype: dict
    """
    message = _message(
        'A REST API operation has been performed.\n'
        '*API Object Type* {} | *Name:* {} | *ID:* {}\n'
        '*User:* {} | *Action:* {} | *Success?* {}'.format(
            data['objectTypeName'],
            data['objectName'],
            data['objectID'],
            data['authorizedUsername'],
            data['restAPIOperationType'],
            data['operationSuccessful']
        ),
        'REST API Operation',
        color='gray',
        image='images/jamfapi_64.png'
    )

    return message


_colors = {
    'gray': '#808080',
    'green': '#008000',
    'purple': '#800080',
    'red': '#ff0000',
    'yellow': '#ffff00'
}


def _message(text, title, title_link=None, color='gray',
             fallback_text=None, image=None, fields=None):
    """Create a Slack formatted message to use with
    :func:`jackalope.slack.send_notification`.

    :param str text: The main text to display in the message.
    :param str title: The title of the message.

    :param str title_link: An optional URL to pass that will convert the title
        into a clickable link.

    :param str color: The color to display in the sidebar of the message. Must
        be of a value in the ``_colors`` dictionary or will default to ``gray``.

    :param str fallback_text: Alternative text to display in place of the
        provided ``text`` value. If not submitted this will be set to the value
        of ``text``.

    :param str image: The filename of an image located in ``/static/images/`` to
        link to with the message. If not submitted this will be set to
        ``general_64.png``.

    :param dict fields: A dictionary of keyword values to populate the optional
        ``fields`` attribute of the Slack message.
    """
    logger.info('Formatting Slack message')

    color = _colors.get(color, _colors['gray'])

    if not fallback_text:
        fallback_text = text

    if not image:
        image = 'images/general_64.png'

    message = {
        "attachments": [
            {
                "fallback": fallback_text,
                "color": color,
                "title": title,
                "title_link": title_link,
                "text": text,
                "fields": list(),
                # "thumb_url": url_for(
                #     'static', filename=image, _external=True),
                "ts": int(time.time()),
                "mrkdwn_in": ["text", "fallback_text"]
            }
        ]
    }

    if isinstance(fields, dict):
        set_fields = list()
        for field in fields.keys():
            set_fields.append({
                "title": field,
                "value": fields[field],
                "short": True
            })
        message['attachments'][0]['fields'] = set_fields

    return message


_webhook_events = {
    'ComputerAdded': _computer_added,
    'ComputerCheckIn': _computer_checkin,
    'ComputerInventoryCompleted': _computer_inventory,
    'JSSShutdown': _jss_shutdown,
    'JSSStartup': _jss_startup,
    'MobileDeviceCheckIn': _mobile_checkin,
    'MobileDeviceEnrolled': _mobile_enrolled,
    'MobileDeviceUnEnrolled': _mobile_unenrolled,
    'PatchSoftwareTitleUpdated': _patch_title_updated,
    'RestAPIOperation': _rest_api_operation
}


def _webhook_notification(webhook):
    """Takes a Jamf Pro webhook event object and returns a formatted Slack
    message from the details if it is in the supported webhook events list.

    If the webhook event is not supported ``None`` will be returned.

    :param webhook: Jamf Pro webhook JSON as dictionary.

    :return: Formatted Slack message.
    :rtype: dict or None
    """
    event_type = webhook['webhook']['webhookEvent']
    if event_type in _webhook_events:
        logger.info('Parsing webhook event: {}'.format(event_type))
        return _webhook_events[event_type](webhook['event'])
    else:
        logger.warning('Did not find a supported webhook event type')
        return None


def send_notification(webhook):
    """Send a formatted Slack message to a channel's inbound webhook.

    :param dict webhook: Jamf Pro webhook JSON data.
    """
    if webhook['webhook']['webhookEvent'] in IGNORED_EVENTS:
        logger.info('Webhook event is listed in ignored events; skipping...')
        return

    message = _webhook_notification(webhook)
    headers = {'Content-Type': 'application/json'}
    try:
        resp = requests.post(SLACK_WEBHOOK_URL, headers=headers, json=message)
    except requests.HTTPError:
        logger.exception(f'Unable to post to Slack: {SLACK_WEBHOOK_URL}')
        raise


def lambda_handler(event, context):
    logger.info(f"Ignored Webhook Events: {', '.join(IGNORED_EVENTS)}")

    if event.get('Records'):
        logging.info('Processing SNS records...')
        for record in event['Records']:
            try:
                event_data = json.loads(record['Sns']['Message'])
            except (TypeError, json.JSONDecodeError):
                logger.exception('Bad Request: No JSON content found')
                return {}

            send_notification(event_data)

    return {}
