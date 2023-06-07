import json
from datetime import datetime, timedelta, timezone

# this script requires a config_file being stores in the same directory

flag = "🇮🇱"  # this symbol has to be in every clause of the config
target_timezone = 3  # this is the time zone which is about to get started after the change
delta = 1  # how many hours are adding? if we go from +2 to +3, input 1, if from +3 to +2, input -1
config_file = "config.json"  # the name of the config file, copy from the config


def update_timezone(date_str: str, target_timezone: int = 0, d: int = 0):
    """
    :param date_str: date from the config
    :param target_timezone: the time zone which will be changed
    :param d: delta how many hours will be added or removed
    :return: updated date
    """
    date_obj = datetime.fromisoformat(date_str)
    desired_timezone = timezone(timedelta(hours=target_timezone))
    date_obj_desired_timezone = date_obj.astimezone(desired_timezone)
    date_obj_with_delta = date_obj_desired_timezone - timedelta(hours=d)
    return date_obj_with_delta.isoformat()


with open(config_file, "r") as f:
    config = json.load(f)

for clause in config['clauses']:
    if flag in clause['title']:
        print(clause['title'])
        for interval in clause['value']['settings']['delivery_guarantees']:
            for key, value in interval.items():
                interval[key] = update_timezone(value, target_timezone, delta)

with open("updated_config.json", "w") as f:
    json.dump(config, f, indent=2)
