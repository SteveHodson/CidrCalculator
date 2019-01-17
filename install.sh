#!/bin/bash

#------------------------------------------------------------------------------
# Installation script for registering the python script with the Lambda Service
# The resulting Lambda Function should be used with CFN to calculate subnet 
# CIDR blocks.
#
# Author: Steve Hodson 
# Date: Jan 2019
# 
# Requires AWSCLI and an appropriate permissions.
#
# Usage: ./install.sh project_name
# Parameters:
# Project_Name - name used to label s3 and cfn assets
#
#------------------------------------------------------------------------------

project=${1:?Please specify a project}
stackname=${project}-utilities-v1

# check for existence of cfn asset bucket
if aws s3 ls "s3://${stackname}" 2>&1 | grep -q 'NoSuchBucket'
then
aws s3 mb s3://${stackname}
else
echo "Using s3://${stackname} to store assets"
fi

# Use a temporary directory to hold all the assets before compression
build_dir=$(mktemp -d)
home=$(pwd)

cp calculator.py ${build_dir}/calculator.py

# Lambda function uses netaddr library
pip install netaddr -t ${build_dir}

# Compress and register the function with Regional Lambda Service
cd ${build_dir}
zip -r ${home}/cidr_calc.zip .

cd ${home}

aws cloudformation package \
  --template-file template.yaml \
  --s3-bucket ${stackname} \
  --output-template-file package-template.yaml > /dev/null 2>&1

aws cloudformation deploy \
  --template-file package-template.yaml \
  --stack-name ${stackname} \
  --capabilities CAPABILITY_IAM

# Clean up
rm -rf ${build_dir}
rm ./package-template.yaml
rm ./cidr_calc.zip