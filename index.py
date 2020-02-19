#!/usr/bin/python3

import yaml
import boto3
from datetime import date
import os


class RunFailed(Exception):
    def __init__(self, m):
        self.message = m

    def __str__(self):
        return self.message


class Config:
    def __init__(self):
        if os.path.dirname(__file__) != "":
            os.chdir(os.path.dirname(__file__))

        # Read config from ini file: .env.yml
        with open(".env", "r") as stream:
            self.config = yaml.load(stream, Loader=yaml.FullLoader)

    def get(self):
        # get config object
        return self.config


class AWSOperation:

    def __init__(self, servicePrefix, asgName):
        self.cfg = Config()
        self.servicePrefix = servicePrefix
        self.asgName = asgName

        self.session = boto3.Session(
            aws_access_key_id=self.cfg.get()['AWS']['ACCESS_KEY'],
            aws_secret_access_key=self.cfg.get()['AWS']['SECRET_KEY'],
            region_name=self.cfg.get()['AWS']['REGION']
        )

        self.ec2 = self.session.client('ec2')
        self.autoscaling = self.session.client('autoscaling')

    def getLatestEC2InstanceID(self):
        response = self.ec2.describe_instances(Filters=[
            {
                'Name': 'tag:service',
                'Values': [
                    self.servicePrefix,
                ]
            },
        ])

        sortedInstances = sorted(
            response['Reservations'], key=lambda k: k['Instances'][0]['LaunchTime'], reverse=True)

        if len(sortedInstances) == 0:
            raise RunFailed(
                'Error: Please set tag:service to your EC2 instance and Auto scaling group.')
        return sortedInstances[0]['Instances'][0]['InstanceId']

    def createAMI(self, instanceId, imageName):
        # return image id
        resp = self.ec2.describe_images(
            Filters=[
                {
                    'Name': 'tag:Name',
                    'Values': [
                        imageName,
                    ]
                },
            ],
        )

        if len(resp['Images']) > 0:
            return resp['Images'][0]['ImageId']

        imageId = self.ec2.create_image(
            InstanceId=instanceId, NoReboot=True, Name=imageName)['ImageId']

        # Add Tags
        self.session.resource('ec2').Image(imageId).create_tags(
            Tags=([
                {'Key': 'service', 'Value': self.servicePrefix},
                {'Key': 'Name', 'Value': imageName}
            ]))

        return imageId

    def waitForAMIAvailable(self, imageId):
        waiter = self.ec2.get_waiter('image_available')
        waiter.wait(ImageIds=[imageId], WaiterConfig={
            'Delay': 60,
            'MaxAttempts': 30
        })

    def isStringExist(self, str, pattern):
        return str.find(pattern) >= 0

    def getLatestLaunchConfig(self):
        response = self.autoscaling.describe_launch_configurations()

        LaunchConfigs = filter(lambda k: self.isStringExist(
            k['LaunchConfigurationName'], self.servicePrefix), response['LaunchConfigurations'])

        sortedLaunchConfigs = sorted(
            LaunchConfigs, key=lambda k: k['CreatedTime'], reverse=True)
        return sortedLaunchConfigs[0]

    def createLaunchConfig(self, oldConfig, amiId):
        # return Launch Config Name
        lcName = appendDate(self.servicePrefix)

        resp = self.autoscaling.describe_launch_configurations(
            LaunchConfigurationNames=[lcName],
        )

        if len(resp['LaunchConfigurations']) > 0:
            return resp['LaunchConfigurations'][0]['LaunchConfigurationName']

        if "SnapshotId" in oldConfig['BlockDeviceMappings'][0]['Ebs']:
            del oldConfig['BlockDeviceMappings'][0]['Ebs']['SnapshotId']

        if oldConfig.get('IamInstanceProfile') != None:
            self.autoscaling.create_launch_configuration(
                LaunchConfigurationName=lcName,
                ImageId=amiId,
                IamInstanceProfile=oldConfig.get('IamInstanceProfile'),
                BlockDeviceMappings=oldConfig['BlockDeviceMappings'],
                InstanceMonitoring={
                    'Enabled': False
                },
                KeyName=oldConfig['KeyName'],
                SecurityGroups=oldConfig['SecurityGroups'],
                InstanceType=oldConfig['InstanceType'],
                AssociatePublicIpAddress=True
            )
        else:
            self.autoscaling.create_launch_configuration(
                LaunchConfigurationName=lcName,
                ImageId=amiId,
                BlockDeviceMappings=oldConfig['BlockDeviceMappings'],
                InstanceMonitoring={
                    'Enabled': False
                },
                KeyName=oldConfig['KeyName'],
                SecurityGroups=oldConfig['SecurityGroups'],
                InstanceType=oldConfig['InstanceType'],
                AssociatePublicIpAddress=True
            )
        return lcName

    def updateASG(self, launchConfigName):
        return self.autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=self.asgName,
            LaunchConfigurationName=launchConfigName)


def appendDate(str):
    return str + "-" + getCurrentDate()


def getCurrentDate():
    today = date.today()
    return today.strftime("%Y-%m-%d")


def main():

    cfg = Config()

    for element in cfg.get()["BACKUP_LIST"]:
        servicePrefix = element["SERVICE_PREFIX"]
        asgName = element["AUTO_SCALING_GROUP_NAME"]

        aws = AWSOperation(servicePrefix, asgName)
        ec2Id = aws.getLatestEC2InstanceID()
        oldConfig = aws.getLatestLaunchConfig()

        AMI_NAME = appendDate(servicePrefix)
        amiId = aws.createAMI(ec2Id, AMI_NAME)
        aws.waitForAMIAvailable(amiId)

        lcName = aws.createLaunchConfig(oldConfig, amiId)
        aws.updateASG(lcName)


if __name__ == '__main__':
    main()
