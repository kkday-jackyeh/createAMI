#!/usr/bin/python3

import yaml
import boto3
from datetime import date, datetime
import os
import datetime as DT


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

        self.session = boto3.Session(
            aws_access_key_id=self.cfg.get()['AWS']['ACCESS_KEY'],
            aws_secret_access_key=self.cfg.get()['AWS']['SECRET_KEY'],
            region_name=self.cfg.get()['AWS']['REGION']
        )

        self.ec2 = self.session.client('ec2')
        self.autoscaling = self.session.client('autoscaling')

    def deleteAMI(self):
        # Get Current AMI List
        resp = self.ec2.describe_images(
            Filters=[
                {
                    'Name': 'tag:service',
                    'Values': [
                        self.servicePrefix,
                    ]
                },
            ],
        )

        # Delete outdated AMI
        for el in resp['Images']:
            amiDate = getDateFromName(el["Name"], self.servicePrefix)
            reservedDate = getPastDate(self.cfg.get()["RESERVED"]["AMI_COUNT"])

            if isEarly(amiDate, reservedDate):
                self.ec2.deregister_image(ImageId=el["ImageId"])

    def deleteLaunchConfig(self):
        # Get Current Launch Config
        response = self.autoscaling.describe_launch_configurations()
        LaunchConfigs = filter(lambda k: isStringExist(
            k['LaunchConfigurationName'], self.servicePrefix), response['LaunchConfigurations'])

        # Delete outdated Launch Config
        for el in LaunchConfigs:
            lcDate = getDateFromName(
                el["LaunchConfigurationName"], self.servicePrefix)
            reservedDate = getPastDate(
                self.cfg.get()["RESERVED"]["LAUNCH_CONFIG_COUNT"])

            if isEarly(lcDate, reservedDate):
                self.autoscaling.delete_launch_configuration(
                    LaunchConfigurationName=el["LaunchConfigurationName"])


def getDateFromName(str, prefix):
    start = len(prefix)+1
    return str[start:]


def isStringExist(str, pattern):
    return str.find(pattern) >= 0


def isEarly(dateStr1, dateStr2):
    try:
        date1 = datetime.strptime(dateStr1, "%Y-%m-%d")
        date2 = datetime.strptime(dateStr2, "%Y-%m-%d")
        return date1 < date2
    except:
        return False


def getCurrentDate():
    today = date.today()
    return today.strftime("%Y-%m-%d")


def getPastDate(days):
    pastDate = date.today() - DT.timedelta(days=days)
    return pastDate.strftime("%Y-%m-%d")


def main():
    cfg = Config()

    for element in cfg.get()["BACKUP_LIST"]:
        servicePrefix = element["SERVICE_PREFIX"]
        asgName = element["AUTO_SCALING_GROUP_NAME"]

        aws = AWSOperation(servicePrefix, asgName)
        aws.deleteAMI()
        aws.deleteLaunchConfig()


if __name__ == '__main__':
    main()
