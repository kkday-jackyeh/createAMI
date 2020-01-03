#!/usr/bin/python3

import configparser
import boto3
from datetime import date


class Config:
    def __init__(self):
        # Read config from ini file: .env
        self.config = configparser.ConfigParser()
        self.config.read('.env')

    def get(self, key):
        # get config by key
        return self.config.get('default', key)


class AWSOperation:

    def __init__(self):
        self.cfg = Config()

        self.session = boto3.Session(
            aws_access_key_id=self.cfg.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=self.cfg.get("AWS_SECRET_KEY"),
            region_name=self.cfg.get("AWS_REGION")
        )

        self.ec2 = self.session.client('ec2')
        self.autoscaling = self.session.client('autoscaling')

    def getLatestEC2InstanceID(self):
        response = self.ec2.describe_instances(Filters=[
            {
                'Name': 'tag:service',
                'Values': [
                    self.cfg.get('SERVICE_PREFIX'),
                ]
            },
        ])

        sortedInstances = sorted(
            response['Reservations'], key=lambda k: k['Instances'][0]['LaunchTime'], reverse=True)

        return sortedInstances[0]['Instances'][0]['InstanceId']

    def createAMI(self, instanceId, imageName):
        # return image id

        imageId = self.ec2.create_image(
            InstanceId=instanceId, NoReboot=True, Name=imageName)['ImageId']

        # Add Tags
        self.session.resource('ec2').Image(imageId).create_tags(
            Tags=([
                {'Key': 'service', 'Value': self.cfg.get('SERVICE_PREFIX')},
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

        LaunchConfigs = filter(lambda k: self.isStringExist(k['LaunchConfigurationName'], self.cfg.get(
            "SERVICE_PREFIX")), response['LaunchConfigurations'])
        sortedLaunchConfigs = sorted(
            LaunchConfigs, key=lambda k: k['CreatedTime'], reverse=True)
        return sortedLaunchConfigs[0]

    def createLaunchConfig(self, oldConfig, amiId):
        # return Launch Config Name
        lcName = appendDate(self.cfg.get("SERVICE_PREFIX"))
        response = self.autoscaling.create_launch_configuration(
            LaunchConfigurationName=lcName,
            ImageId=amiId,
            KeyName=oldConfig['KeyName'],
            SecurityGroups=oldConfig['SecurityGroups'],
            InstanceType=oldConfig['InstanceType'],
        )

        return lcName

    def updateASG(self, launchConfigName):
        return self.autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=self.cfg.get("AUTO_SCALING_GROUP_NAME"),
            LaunchConfigurationName=launchConfigName)


def appendDate(str):
    return str + "-" + getCurrentDate()


def getCurrentDate():
    today = date.today()
    return today.strftime("%Y-%m-%d")


def main():

    cfg = Config()

    aws = AWSOperation()
    # ec2Id = aws.getLatestEC2InstanceID()
    # oldConfig = aws.getLatestLaunchConfig()

    # AMI_NAME = appendDate(cfg.get("SERVICE_PREFIX"))
    # amiId = aws.createAMI(ec2Id, AMI_NAME)
    # aws.waitForAMIAvailable(amiId)

    # lcName = aws.createLaunchConfig(oldConfig, amiId)
    # lcName = 'plone-2020-01-03'
    # aws.updateASG(lcName)


if __name__ == '__main__':
    main()
