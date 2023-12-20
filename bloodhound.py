import boto3
import os
import json
from dotenv import load_dotenv

# Import WebClient from Python SDK (github.com/slackapi/python-slack-sdk)
from slack_sdk import WebClient

load_dotenv()

STUDENT_REGIONS = [
    "eu-central-1",
    "eu-west-1",
    "eu-west-2",
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
]


def create_session(region):
    return boto3.Session(profile_name="bloodhound", region_name=region)


def search_regions_for_rds_resources(session):
    rds_instances = []
    print(f"Sniffing out rds resources in {session.region_name}...")
    rds = session.client("rds")
    response = rds.describe_db_instances()
    for dbinstance in response["DBInstances"]:
        rds_instances.append(dbinstance["DBInstanceIdentifier"])
    return {"rds": rds_instances}


def search_regions_for_ec2_resources(session):
    """
    TODO: modify the parsing logic here from the describe_instances() call,
    https://serverfault.com/questions/749118/
    Instances spun up at the same time will be in the same reservationId more than likely.
    Instances spun up individually will have their own reservationId
    """
    ec2_instances = []
    print(f"Sniffing out ec2 resources in {session.region_name}...")
    ec2 = session.client("ec2")
    response = ec2.describe_instances()
    try:
        # Instances spun up at the same time will be listed in the same Reservation
        if len(response["Reservations"]) == 1:
            for ec2instance in response["Reservations"][0]["Instances"]:
                if ec2instance["State"]["Name"] in ("stopped", "terminated"):
                    continue
                ec2_instances.append(ec2instance["InstanceId"])
        # Indvidual instances will appear in their own Reservation
        else:
            for ec2instance in response["Reservations"]:
                if ec2instance["Instances"][0]["State"]["Name"] in ("stopped", "terminated"):
                    continue
                ec2_instances.append(ec2instance["Instances"][0]["InstanceId"])
    except IndexError:
        return {"ec2": []}
    return {"ec2": ec2_instances}


def format_message(resources):
    message = ":dog2: Woof! Woof! :dog2:\n Bloodhound found the following resources in use: \n"
    for region in resources.keys():
        if len(resources[region]["ec2"]) == 0 and len(resources[region]["rds"]) == 0:
            continue
        message += f'- *{region.upper()}*: {len(resources[region]["ec2"])} ec2 instances, {len(resources[region]["rds"])} rds instances\n'
    message += f"Please stop or terminate all unneeded resources!"
    return message


def send_slack_message(message):
    channel_id = os.environ.get("CHANNEL_ID")
    client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
    client.chat_postMessage(channel=channel_id, text=message)


def main():
    resources_in_regions = {}
    print(f"Going hunting in regions {STUDENT_REGIONS}")
    for region in STUDENT_REGIONS:
        session = create_session(region)
        resources_in_regions[region] = search_regions_for_ec2_resources(session)
        resources_in_regions[region].update(search_regions_for_rds_resources(session))
    message = format_message(resources_in_regions)
    print(message)
    send_slack_message(message)


if __name__ == "__main__":
    main()
