import datetime
import hashlib
import random
import string


def generate_random_md5():
    random_string = "".join(random.choices(string.ascii_letters + string.digits, k=32))
    md5_hash = hashlib.md5()
    md5_hash.update(random_string.encode("utf-8"))
    return md5_hash.hexdigest()


def generate_datetime() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
