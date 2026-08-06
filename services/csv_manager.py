import csv
import os

FILE_PATH = "data/tasks.csv"

HEADERS = [
    "id",
    "user_id",
    "title",
    "priority",
    "status",
    "deadline",
    "category",
    "tags",
    "created_at"
]


def init_csv():

    os.makedirs(
        "data",
        exist_ok=True
    )

    if not os.path.exists(FILE_PATH):

        with open(
            FILE_PATH,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)
            writer.writerow(HEADERS)



def save_task(data):

    with open(
        FILE_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)
        writer.writerow(data)



def read_tasks():

    if not os.path.exists(FILE_PATH):
        return []

    with open(
        FILE_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        return list(reader)