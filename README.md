# Subnet CIDR Lambda function
This cloudformation custom resource utility lambda function will calculate all the subnet CIDR ranges for a given VPC Cidr range.
## Introduction
Usually VPCs are broken up into subnets whose IP allocation size are equally distributed across the VPC. For instance a VPC whose CIDR block is /21 might have subnets whose IP allocations are all /24. 
Whilst this approach works it does not take into account the functional use of the subnets.  There is another approach that divides the initial IP allocation by a half and recursively divides one of those halves by a half.  This approach will create IP allocation spaces each half the size of the previous.  In my experience a persistence subnet would require less nodes than say the public subnet which itself would require less nodes than a private subnet.
Here an example of a VPC with three layers; note the relative sizes of the boxes refer to the relative sizes of the IP allocations.
![Example VPC](https://github.com/SteveHodson/markdown-here/raw/master/src/common/images/CidrCalculator1.png "Example VPC")

## Parameters
This function requires the following parameters:
* VpcCidrBlock - a string defining the CIDR block used by the VPC e.g. 10.0.0.0/24
* Zones - number of availability zones that the VPC will span.
* Layers - list of names of the functional layers of the VPC.

NB The order of the Layers is important with the first mentioned getting the largest share of the IP allocation.

## Output
The output from this function will be a dictionary object containing the calculated CIDR blocks for the functional layers and comma delimited lists 
For example here is the output from a CIDR calculation for a VPC (cidr_block=10.0.0.0/16, zones=3 and layers="public,private"
```sh
{'public': '10.0.0.0/17', 'publicList': '10.0.0.0/19,10.0.32.0/19,10.0.64.0/19,10.0.96.0/19', 'private': '10.0.128.0/18', 'privateList': '10.0.128.0/20,10.0.144.0/20,10.0.160.0/20,10.0.176.0/20'}
```
This output is then to be used within your cloudformation subnet creation stacks.
## Use in Cloudformation
This lambda function has been written to extend the functionality of cloudformation in relation to calculating subbnet cidr ranges used in the creation of subnets.  An example written in yaml is shown.
```yaml
CidrBlockCalculation:
    Type: Custom::SubnetCidrCalculator
    Properties:
        ServiceToken: !Sub arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:SubnetCidrCalculator
        VpcCidrBlock: 10.0.0.0/16
        Layers: [public, private]
        Zones: 3
```
## Build
```sh
./install.sh [project_name]
```
The installation script expects a unique name that will be used when creating the cloudformation stack.  The choice of creating this separately from the VPC creation is that this utility function can be used for many VPC creation stacks.
This can be tested in the AWS MAnagement Console using the following json:
```javascript
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
```
Note: Number of zones supported is between 1 and 5 and whilst the solution itself won;t break at higher values it will prove wasteful as AWS has at most 5 AZs per region.
## Permissions
The lambda function uses the BasicExecutionRole which accesses CloudWatch only.
## License
Feel free to use this little tool anyway you wish.
