#!/usr/bin/env python3
"""Validate the design profile contract without third-party dependencies.

This is a build-time/documentation checker.  The compiled client does not yet
consume profile files; keeping this validator strict prevents examples from
drifting away from the versioned contract.
"""
import json
import sys
from pathlib import Path

MAX_BYTES = 256 * 1024
MAX_DEPTH = 32


class ValidationError(ValueError):
    pass


def pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("duplicate object key: %s" % key)
        result[key] = value
    return result


def depth(value, level=0):
    if level > MAX_DEPTH:
        raise ValidationError("profile nesting exceeds %d levels" % MAX_DEPTH)
    if isinstance(value, dict):
        for item in value.values():
            depth(item, level + 1)
    elif isinstance(value, list):
        for item in value:
            depth(item, level + 1)


def string_field(obj, name):
    value = obj.get(name)
    if not isinstance(value, str) or not value:
        raise ValidationError("%s must be a non-empty string" % name)


def validate(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValidationError("profile exceeds %d bytes" % MAX_BYTES)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs_no_duplicates)
    except UnicodeDecodeError:
        raise ValidationError("profile must be UTF-8")
    except json.JSONDecodeError as exc:
        raise ValidationError("invalid JSON: %s" % exc)
    depth(value)
    if not isinstance(value, dict):
        raise ValidationError("profile root must be an object")
    allowed = {"schema_version", "filters", "masks"}
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError("unknown field: %s" % sorted(unknown)[0])
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise ValidationError("schema_version must be 1")
    for section, required in (("filters", ("table", "where")), ("masks", ("table", "column"))):
        entries = value.get(section, [])
        if not isinstance(entries, list):
            raise ValidationError("%s must be an array" % section)
        seen_masks = set()
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValidationError("%s[%d] must be an object" % (section, index))
            fields = set(required)
            if section == "filters":
                allowed_entry = fields
            else:
                allowed_entry = fields | {"preset", "expression"}
                if ("preset" in entry) == ("expression" in entry):
                    raise ValidationError("masks[%d] requires exactly one of preset/expression" % index)
            unknown_entry = set(entry) - allowed_entry
            if unknown_entry:
                raise ValidationError("unknown field %s in %s[%d]" % (sorted(unknown_entry)[0], section, index))
            for field in required:
                string_field(entry, field)
            if section == "masks":
                mask_key = (entry.get("table"), entry.get("column"))
                if mask_key in seen_masks:
                    raise ValidationError("duplicate mask target: %s.%s" % mask_key)
                seen_masks.add(mask_key)
                string_field(entry, "preset" if "preset" in entry else "expression")


def main(argv):
    if len(argv) < 2:
        print("usage: validate_profile.py PROFILE [...]", file=sys.stderr)
        return 2
    try:
        for path in argv[1:]:
            validate(path)
    except (OSError, ValidationError) as exc:
        print("profile validation failed: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
