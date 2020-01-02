#!/usr/bin/python3

import configparser
import boto3
import time


class Config:
    def __init__(self):
        # Read config from ini file: .env
        self.config = configparser.ConfigParser()
        self.config.read('.env')
        # print(self.config.get("AWS_ACCESS_KEY"))

    def get(self, key):
        return self.config.get('default', key)


class AWSOperation:

    def __init__(self):
        self.cfg = Config()
        self.ec2 = boto3.client(
            'ec2',
            aws_access_key_id=self.cfg.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=self.cfg.get("AWS_SECRET_KEY"),
            region_name=self.cfg.get("AWS_REGION")
        )

        self.autoscaling = boto3.client(
            'autoscaling',
            aws_access_key_id=self.cfg.get("AWS_ACCESS_KEY"),
            aws_secret_access_key=self.cfg.get("AWS_SECRET_KEY"),
            region_name=self.cfg.get("AWS_REGION")
        )

    def getEC2InstanceID(self):
        response = self.ec2.describe_instances(Filters=[
            {
                'Name': 'tag:belongTo',
                'Values': [
                    'jack',
                ]
            },
        ])
        return response['Reservations'][0]['Instances'][0]['InstanceId']

    def createAMI(self, instanceId, imageName):
        return self.ec2.create_image(
            InstanceId=instanceId, NoReboot=True, Name=imageName)

    def getAMIState(self, imageId):
        return self.ec2.describe_images(
            Filters=[{
                'Name': 'image-id',
                'Values': [imageId]
            }])['Images'][0]['State']

    def deleteOldAMI(self, imageName):
        imageId = self.ec2.describe_images(
            Filters=[{
                'Name': 'name',
                'Values': [imageName]

            }])['Images'][0]['ImageId']

        return self.ec2.deregister_image(ImageId=imageId)

    def getOldLaunchConfig(self):
        response = self.autoscaling.describe_launch_configurations(
            LaunchConfigurationNames=[
                self.cfg.get("LAUNCH_CONFIGURATION_NAME"),
            ])
        return response['LaunchConfigurations'][0]

    def deleteOldLaunchConfig(self):
        return self.autoscaling.delete_launch_configuration(LaunchConfigurationName=self.cfg.get("LAUNCH_CONFIGURATION_NAME"),)

    def createLaunchConfig(self, oldConfig, amiId):
        response = self.autoscaling.create_launch_configuration(
            LaunchConfigurationName=self.cfg.get("LAUNCH_CONFIGURATION_NAME"),
            ImageId=amiId,
            KeyName=oldConfig['KeyName'],
            SecurityGroups=oldConfig['SecurityGroups'],
            InstanceType=oldConfig['InstanceType'],
        )

        return response


def main():

    cfg = Config()

    aws = AWSOperation()
    ec2Id = aws.getEC2InstanceID()
    amiId = aws.createAMI(ec2Id, cfg.get("AMI_NAME"))

    for i in range(60):
        state = aws.getAMIState(amiId)
        if state == 'available':
            break

        time.sleep(60)

    oldConfig = aws.getOldLaunchConfig()
    aws.deleteOldLaunchConfig()
    aws.deleteOldAMI(cfg.get("AMI_NAME"))
    aws.createLaunchConfig(oldConfig, amiId)


if __name__ == '__main__':
    main()
