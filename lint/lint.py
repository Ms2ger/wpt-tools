from __future__ import print_function, unicode_literals

from typing import Callable, Tuple, Optional, Mapping, Set, List, Text

import argparse
import fnmatch
import os
import re
import subprocess
import sys

from collections import defaultdict

from six import iteritems, itervalues

ERROR_MSG = ""

Error = Tuple[Text, Text, Optional[int]]
Whitelist = Mapping[bytes, Mapping[Text, Set[int]]]

def check_path_length(repo_root, path):
    # type: (bytes, bytes) -> List[Error]
    if len(path) + 1 > 150:
        return [("PATH LENGTH", "/%s longer than maximum path length (%d > 150)" % (path, len(path) + 1), None)]
    return []

def parse_whitelist_file(filename):
    # type: (bytes) -> Whitelist
    """
    Parse the whitelist file at `filename`, and return the parsed structure.
    """

    data = defaultdict(lambda:defaultdict(set))  # type: Whitelist

    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [item.strip() for item in line.split(":")]
            if len(parts) == 2:
                error_type, file_match = parts
                line_number = None
            else:
                error_type, file_match, line_nr = parts
                line_number = int(line_nr)

            file_match_bytes = file_match.encode('utf-8')
            data[file_match_bytes][error_type].add(line_number)

    return data


def filter_whitelist_errors(data, path, errors):
    # type: (Whitelist, bytes, List[Error]) -> List[Error]
    """
    Filter out those errors that are whitelisted in `data`.
    """

    whitelisted = [False for item in range(len(errors))]

    for file_match, whitelist_errors in iteritems(data):
        if fnmatch.fnmatch(path, file_match):
            for i, (error_type, msg, line) in enumerate(errors):
                if "*" in whitelist_errors:
                    whitelisted[i] = True
                elif error_type in whitelist_errors:
                    allowed_lines = whitelist_errors[error_type]
                    if None in allowed_lines or line in allowed_lines:
                        whitelisted[i] = True

    return [item for i, item in enumerate(errors) if not whitelisted[i]]

def output_errors(errors):
    # type: (List[Error]) -> None
    for error_type, error, line_number in errors:
        print("%s: %s" % (error_type, error))

def output_error_count(error_count):
    # type: (defaultdict[Text, int]) -> None
    if not error_count:
        return

    by_type = " ".join("%s: %d" % item for item in error_count.items())
    count = sum(error_count.values())
    if count == 1:
        print("There was 1 error (%s)" % (by_type,))
    else:
        print("There were %d errors (%s)" % (count, by_type))


def lint(repo_root, paths):
    # type: (bytes, List[bytes]) -> int
    error_count = defaultdict(int)  # type: defaultdict[Text, int]
    last = None

    whitelist = parse_whitelist_file(os.path.join(repo_root, b"lint.whitelist"))

    def run_lint(path, fn, last):
        # type: (bytes, Callable[[bytes, bytes], List[Error]], Optional[Tuple[Text, bytes]]) -> Optional[Tuple[Text, bytes]]
        errors = filter_whitelist_errors(whitelist, path, fn(repo_root, path))
        if errors:
            last = (errors[-1][0], path)

        output_errors(errors)
        for error_type, error, line in errors:
            error_count[error_type] += 1
        return last

    for path in paths:
        abs_path = os.path.join(repo_root, path)
        if not os.path.exists(abs_path):
            continue
        for path_fn in path_lints:
            last = run_lint(path, path_fn, last)

    output_error_count(error_count)
    if error_count:
        print(ERROR_MSG % (last[0], last[1], last[0], last[1]))
    return sum(itervalues(error_count))

path_lints = [check_path_length]  # type: List[Callable[[bytes, bytes], List[Error] ]]
