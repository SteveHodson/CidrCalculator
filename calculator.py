'''
A custom resource that calculates the subnet cidr blocks
used when creating a VPC.

Sample Cloudformation
CidrBlockCalculation:
    Type: Custom::SubnetCidrCalculator
    Properties:
        ServiceToken: ARN for the lambda function, SubnetCidrCalculator
        VpcCidrBlock: Cidr Block 
        Layers: List of names for the network layers
        Zones: Number of AZ to be used
The number of zones have to lie between 2 and 4 inclusive.

Example:
CidrBlockCalculation:
    Type: Custom::SubnetCidrCalculator
    Properties:
        ServiceToken: !Sub arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:SubnetCidrCalculator
        VpcCidrBlock: 10.0.0.0/16
        Layers: [public, private]
        Zones: 3

Author: Steve Hodson
Date: Jan 2019

To Test use:
{
  "StackId": "arn:aws:cloudformation:eu-west-1:EXAMPLE/stack-name/guid",
  "ResponseURL": "http://pre-signed-S3-url-for-response",
  "ResourceProperties": {
    "VpcCidrBlock": "10.0.0.0/16",
    "Zones": "2",
    "Layers": [
        "public",
        "private"
        ]
  },
  "RequestType": "Create",
  "ResourceType": "Custom::TestResource",
  "RequestId": "unique id for this create request",
  "LogicalResourceId": "MyTestResource"
}

'''
import json
import uuid
import logging
import math

from botocore.vendored import requests
from netaddr import IPNetwork

SUCCESS = "SUCCESS"
FAILED = "FAILED"
PHYSICAL_RESOURCE_ID = f"SubnetCidrCalculator-{uuid.uuid1()}"

logger = logging.getLogger()
logger.level(logging.INFO)

def handler(event, context):
    '''
    Creates a dictionary of cidr block values to be used by the 
    calling CFN stack.  This handler is only used when the 
    stack is in a 'Create' mode.  Once the dictionary of 
    cidr blocks has been created it is passed back to the 
    calling stack.

    Parameters
    ----------
    event: aws lambda event object
    context: aws lambda context object
    '''
    # There is nothing to do for a update/delete request
    if event['RequestType'] != 'Create':
        return send_response(event, context, SUCCESS, 
        reason=f"Calling the {context.getFunctionName()} when NOT creating a VPC.")

    # Variables used in this algorithm
    response_data = {}
    properties = event.get("ResourceProperties", {})
    network_cidr = properties["VpcCidrBlock"]
    network_layers = properties["Layers"]
    availability_zones = int(properties["Zones"])

    # get the network address for a given network_cidr
    nw = IPNetwork(network_cidr)
    # check the minimum and maximum prefixes allowed by AWS VPC
    cidr_prefix = nw.prefixlen

    # check the parameters
    params = {
        'cidr_prefix': cidr_prefix,
        'layers_len': len(network_layers),
        'availability_zones': availability_zones
        }
    try:
        check_parameters(**params)
    except ValueError as err:
        logger.error(err)
        return send_response(
            event, context, FAILED,
            reason=f"{err.__class__.__name__}: {err}"
            )

    # calculate the VPC Network as the given Network IP may not
    # be the Network IP address as calculated using the hostmask
    network_ip = nw.network
    network = IPNetwork(network_ip)
    network.prefixlen = cidr_prefix
    az_modifier = math.ceil(math.log(availability_zones)/math.log(2))
    
    try:
        for i, layer in enumerate(network_layers, 1):
            tmp_prefix = cidr_prefix + i
            network_by_layer = list(network.subnet(tmp_prefix))
            response_data[layer] = str(network_by_layer[0])
            network = network_by_layer[1]
            network_by_az = list(network_by_layer[0].subnet(tmp_prefix+az_modifier))
            response_data[f"{layer}List"] = ",".join([str(nw) for nw in network_by_az])
    except Exception as ex:
        logger.error(ex)
        return send_response(
            event, context, FAILED,
            reason=f"{ex.__class__.__name__}: {ex}"
            )

    logger.info(response_data)
    return send_response(event, context, SUCCESS, response_data=response_data)

def check_parameters(**params):
    if (params['cidr_prefix'] < 16 or params['cidr_prefix'] > 28):
        raise ValueError('Illegal prefix number used.  Please use a number between 16 and 28 inclusive')
    if (params['layers_len'] < 2 or params['layers_len'] > 5):
        raise ValueError('Illegal number of network layers used.  Please use a list containing between 2 and 5 layers inclusive')
    if (params['availability_zones'] < 1 or params['availability_zones'] > 4):
        raise ValueError('Illegal number of availbility zones used.  Please use a number between 2 and 4 inclusive')

def send_response(event, context, response_status, response_data=None, reason=None):
    """This function will wrap a response into a json object and send back to 
    cloudformation for use within the calling stack.
    
    Parameters
    ----------
    event: aws lambda event object
    context: aws lambda context object
    response_status: string
        SUCCESS or FAILURE
        Status sent back to Cloudformation and will cause the 
        current stack process to continue or to stop.
    response_data: dictionary
        Data structure containing any data required by the cloudformation 
        stack.
    reason: string
        Bespoke message usually used for logging errors.
    Exceptions
    ----------
    HTTPError 
    """
    default_reason = (
        f"See the details in CloudWatch Log group {context.log_group_name} "
        f"Stream: {context.log_stream_name}"
    )

    response_body = json.dumps(
        {
            "Status": response_status,
            "Reason": str(reason) + f".. {default_reason}" if reason else default_reason,
            "PhysicalResourceId": PHYSICAL_RESOURCE_ID,
            "StackId": event["StackId"],
            "RequestId": event["RequestId"],
            "LogicalResourceId": event["LogicalResourceId"],
            "Data": response_data,
        }
    )

    logger.info(f"ResponseURL: {event['ResponseURL']}", )
    logger.info(f"ResponseBody: {response_body}")

    headers = {"Content-Type": "", "Content-Length": str(len(response_body))}

    response = requests.put(event["ResponseURL"], data=response_body, headers=headers)
    try:
        response.raise_for_status()
        logger.info(f"Status code: {response.reason}")
    except requests.HTTPError:
        logger.exception(f"Failed to send CFN response. {response.text}")
        raise
