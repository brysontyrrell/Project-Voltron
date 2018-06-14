# Project Voltron

A concept for a modular plugin architecture for Jamf Pro available through the [AWS Serverless Application Repository](https://aws.amazon.com/serverless/serverlessrepo/).

## How it works

{ Todo: Insert some pretty diagrams to illustrate }

## Individual components:

* Webhook Processor
    - Creates an API Gateway to receive webhook events.
    - Creates SNS topics to publish events to.
    
* Slack Notifier
    - Attach to a Webhook Processor to send notifications to a Slack channel.

* Poller
    - Perform periodic scans of the REST API.

* Populator
    - Attach to a Webhook Processor.
        + Computer/Mobile Devices only.
    - Perform a return PUT operation on a device record if the serial number exists in an S3 data source.
    - Requires a JSON/CSV file in a S3 bucket.

* Custom HTTP Passthrough
    - Passthrough posting of a Jamf Pro webhook to another HTTP resource.
    - Can customize the passthrough request headers.

* Custom Function
    - Provide the name of another Lambda function in your AWS account to invoke on an event.
