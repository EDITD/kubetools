from hashlib import sha1


def make_dns_safe_name(name):
    return name.replace('_', '-')


def get_hash(name):
    if isinstance(name, str):
        name = name.encode()
    return sha1(name).hexdigest()[:6]


def copy_and_update(base, *extras):
    if base:
        new_base = base.copy()
    else:
        new_base = {}

    for extra in extras:
        if extra:
            new_base.update(extra)
    return new_base
