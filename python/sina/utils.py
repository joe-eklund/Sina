"""Module for handling miscellany."""
from __future__ import print_function
import logging
import json
import os
import errno
import uuid
import csv
import time
import datetime
from numbers import Number

from multiprocessing.pool import ThreadPool
from collections import OrderedDict

import sina.model as model

LOGGER = logging.getLogger(__name__)
MAX_THREADS = 8


def import_many_jsons(factory, json_list):
    """
    Import multiple JSON documents into a supported backend.

    Lazily multithreaded for backends that support parallel ingestion.

    :param factory: The factory used to perform the import.
    :param json_list: List of filepaths to import from.
    """
    LOGGER.info('Importing json list: {}'.format(json_list))
    if factory.supports_parallel_ingestion:
        LOGGER.debug('Factory supports parallel ingest, building thread pool.')
        arg_tuples = [(factory, x) for x in json_list]
        pool = ThreadPool(processes=min(len(json_list), MAX_THREADS))
        pool.map(_import_tuple_args, arg_tuples)
        pool.close()
        pool.join()
    else:
        LOGGER.debug('Factory does not support parallel ingest.')
        for json_file in json_list:
            import_json(factory, json_file)


def _import_tuple_args(unpack_tuple):
    """Unpack args to allow using import_json with ThreadPools in <Python3."""
    import_json(unpack_tuple[0], unpack_tuple[1])


def import_json(factory, json_path):
    """
    Import one JSON document into a supported backend.

    :param factory: The factory used to perform the import.
    :param json_path: The filepath to the json to import.
    """
    LOGGER.debug('Importing {}'.format(json_path))
    with open(json_path) as file:
        data = json.load(file)
    runs = []
    records = []
    local = {}
    for entry in data.get('records', []):
        type = entry['type']
        if 'id' in entry:
            id = entry['id']
        else:
            id = str(uuid.uuid4())
            try:
                local[entry['local_id']] = id
                # Save the UUID to be used for record generation
                entry['id'] = id
            except KeyError:
                raise ValueError("Record requires one of: local_id, id: {}"
                                 .format(entry))
        if type == 'run':
            runs.append(model.generate_run_from_json(json_input=entry))
        else:
            records.append(model.generate_record_from_json(json_input=entry))
    factory.createRunDAO().insert_many(runs)
    factory.createRecordDAO().insert_many(records)
    relationships = []
    for entry in data.get('relationships', []):
        subj, obj = _process_relationship_entry(entry=entry, local_ids=local)
        relationships.append(model.Relationship(subject_id=subj,
                                                object_id=obj,
                                                predicate=entry['predicate']))
    factory.createRelationshipDAO().insert_many(relationships)


def _process_relationship_entry(entry, local_ids):
    """
    Read a JSON Object from Relationships and extract the subject and object.

    This helper method handles replacing local_ids with global ones, as well as
    telling which is in use, and raises any necessary errors.

    :param entry: The JSON object to be processed
    :param local_ids: The dictionary of local_id:global_id pairs

    :returns: A tuple of (subject_id, object_id)

    :raises ValueError: if the relationship doesn't have the required
                        components, or a local_id has no paired global_id.
    """
    LOGGER.debug('Processing relationship entry: {}'.format(entry))
    try:
        subj = local_ids[entry['local_subject']] if 'subject' not in entry else entry['subject']
        obj = local_ids[entry['local_object']] if 'object' not in entry else entry['object']
    except KeyError:
        if not any(subj in ("local_subject", "subject") for subj in entry):
            msg = ("Relationship requires one of: subject, "
                   "local_subject: {}".format(entry))
            LOGGER.error(msg)
            raise ValueError(msg)
        if not any(obj in ("local_object", "object") for obj in entry):
            msg = ("Relationship requires one of: object, "
                   "local_object: {}".format(entry))
            LOGGER.error(msg)
            raise ValueError(msg)
        msg = ("Local_subject and/or local_object must be the "
               "local_id of a Record within file: {}"
               .format(entry))
        LOGGER.error(msg)
        raise ValueError(msg)
    return (subj, obj)


def export(factory, id_list, scalar_names, output_type, output_file=None):
    """
    Export records and corresponding scalars.

    :param factory: The DAOFactory to use.
    :param id_list: The list of record ids to export.
    :param scalar_names: The list of scalars to output for each record.
    :param output_type: The type of output to export to. Acceptable values are:
                        csv
    :param output_file: The file to output. If None, then default to a
                        timestamped output.
    """
    LOGGER.info('Exporting to type {}.'.format(output_type))
    LOGGER.debug('Exporting <id_list={}, scalar_names={}, output_file={}>.'
                 .format(id_list, scalar_names, output_type, output_file))
    if not output_type == 'csv':
        msg = 'Given "{}" for output_type and it must be one of the '\
              'following: csv'.format(output_type)
        LOGGER.error(msg)
        raise ValueError(msg)
    if not output_file:
        output_file = ('output_' +
                       (datetime.datetime.fromtimestamp(
                        time.time()).strftime('%Y-%m-%d_%H-%M-%S')) +
                       '.csv')
        LOGGER.debug('Using default output file: {}.'.format(output_file))
    data_to_export = OrderedDict()
    record_dao = factory.createRecordDAO()
    for id in id_list:
        data_to_export[id] = record_dao.get_scalars(id=id,
                                                    scalar_names=scalar_names)
    _export_csv(data=data_to_export,
                scalar_names=scalar_names,
                output_file=output_file)


def _export_csv(data, scalar_names, output_file):
    """
    Export records and corresponding scalars to a csv file.

    :param data: The dictionary of record ids to list of scalars to export.
                 Use OrderedDict (as in export()) to preserve order.
    :param scalar_names: The list of scalars names to output. Used for header.
    :param output_file: The file to output.
    """
    LOGGER.debug('About to write data to csv file: {}'.format(output_file))
    header = ['id'] + scalar_names
    with open(output_file, 'w') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for run, dataset in data.items():
            # Each entry is a dict of scalars
            if dataset:
                writer.writerow([run] + [dataset[scalar]['value'] for scalar in scalar_names])


def parse_data_string(data_string):
    """
    Parse a string into (name, DataRange) tuples for use with data_query().

    Ex: "speed=(3,4] max_height=(3,4]" creates two DataRanges. They are both
    min exclusive, max inclusive, and have a range of 3.0 to 4.0. They are then
    paired up with their respective names and returned as:
    [("speed", range_1), ("max_height", range_2)]

    :param data_string: A string of space-separated range descriptions

    :raises ValueError: if given a badly-formatted range, ex: '<foo>=,2]'

    :returns: a list of tuples: (name, DataRange).

    """
    LOGGER.debug('Parsing string <{}> into DataRange objects.'
                 .format(data_string))
    raw_data = filter(None, data_string.split(" "))
    clean_data = []

    for entry in raw_data:
        components = entry.split("=")
        name = components[0]

        # Make sure scalar's of the form <foo>=<bar>
        if len(components) < 2 or len(components[1]) == 0:
            raise ValueError('Bad syntax for scalar \'{}\'.'.format(name))
        val_range = components[1].split(",")
        data_range = DataRange()

        if len(val_range) == 1:
            val = val_range[0]
            # If a user types 4, it arrives as "4", thus the cast
            # If they give us '4', it arrives as "'4'", thus the strip
            try:
                val = float(val)
            except ValueError:
                val = val.strip("'").strip('"')
            data_range.set_equal(val)
            clean_data.append((name, data_range))
        elif is_grouped_as_range(components[1]) and len(val_range) == 2:
            data_range.set_min(val_range[0])
            data_range.set_max(val_range[1])
            clean_data.append((name, data_range))
        else:
            raise ValueError('Bad specifier in range for {}'
                             .format(name))

    return clean_data


def parse_scalars(scalar_args):
    """
    Parse commandline input into ScalarRange object(s).

    Ex: "speed=[3,4), speed=[3,4)" returns two ScalarRanges, each  with the
    name "speed." The resulting ScalarRange is min inclusive, max exclusive,
    and has a range of 3.0 to 4.0.

    :params scalar_args: The "scalar" argument provided by the user

    :raises ValueError: if given a badly-formatted range, ex: '<foo>=,2]'

    :returns: a list of ScalarRange objects.

    """
    LOGGER.debug('Parsing command line args <{}> into ScalarRange objects.'
                 .format(scalar_args))
    raw_scalars = filter(None, scalar_args.strip("\"").split(" "))
    clean_scalars = []

    for entry in raw_scalars:
        components = entry.split("=")
        name = components[0]

        # Make sure scalar's of the form <foo>=<bar>
        if len(components) < 2 or len(components[1]) == 0:
            raise ValueError('Bad syntax for scalar \'{}\'.'.format(name))
        val_range = components[1].split(",")
        scalar = ScalarRange(name)

        if len(val_range) == 1:
            scalar.set_equal(val_range[0])
            clean_scalars.append(scalar)
        elif is_grouped_as_range(components[1]) and len(val_range) == 2:
            scalar.set_min(val_range[0])
            scalar.set_max(val_range[1])
            clean_scalars.append(scalar)
        else:
            raise ValueError('Bad specifier in range for {}. See -h'
                             .format(name))

    return clean_scalars


def is_grouped_as_range(range_string):
    """
    Return whether a string, ex: (2,3], begins & ends in valid range-grouping characters.

    :param range_string: The string to check

    :returns: True if the string has valid range-grouping, else False
    """
    LOGGER.debug('Checking if the following has proper range characters: {}'
                 .format(range_string))
    open_identifier = ["[", "("]
    close_identifier = ["]", ")"]

    if len(range_string) < 2:
        return False
    if range_string[0] not in open_identifier or range_string[-1] not in close_identifier:
        return False
    return True


def create_file(path):
    """
    Check if a file exists.

    If it does not, creates an empty file with the given path. Will create
    directories that don't exist in the path.

    :param path: (string, req) The path to create.

    :raises OSError: This shouldn't happen, but unexpected OSErrors will get
        raised (we catch EEXist already).

    """
    LOGGER.debug('Creating new file: {}'.format(path))
    if not os.path.exists(path):
        # Make directory
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as err:
            if err.errno == errno.EEXIST:
                msg = ('Directory already created, or race condition? Check '
                       'path: {}'.format(path))
                LOGGER.error(msg)
            else:
                msg = 'Unexpected OSError: {}'.format(err)
                LOGGER.error(msg)
                raise OSError(msg)
        # Make file
        with open(path, 'a+') as f:
            f.close()


def get_example_path(relpath, suffix="-new",
                     example_dirs=["/collab/usr/gapps/wf/examples/",
                                   os.path.realpath(os.path.join(os.path.dirname(__file__),
                                                    "../../examples/"))]):
    """
    Return the fully qualified path name for the appropriate example data store and
    raises an exception if none is found.

    This function checks the paths listed in <example_dirs> for the file specified
    with <relpath>.

    If $SINA_TEST_KERNEL is set, it will initially append <suffix> to relpath's
    filename, ex foo/bar.txt becomes foo/bar<suffix>.txt. If it doesn't find
    anything, it reverts (so it looks for relpath both with and without the suffix).

    The order of example_dirs is important; as soon as something that matches is
    found, the function returns.

    :param relpath: The path, relative to the example_dirs, of the data store
    :param suffix: The test filename suffix
    :param example_dirs: A list of fully qualified paths to root directories
        containing example data
    :returns: The path to the appropriate example data store
    :raises ValueError: if an example data store file does not exist
    """
    LOGGER.debug("Retrieving example data store path: {}, {}, {}".
                 format(relpath, suffix, example_dirs))

    dirs = [example_dirs] if isinstance(example_dirs, str) else example_dirs

    paths = [relpath]
    if os.getenv("SINA_TEST_KERNEL") is not None:
        base, ext = os.path.splitext(relpath)
        paths.insert(0, "{}{}{}".format(base, suffix, ext))

    filename = None
    for db_path in paths:
        for root in dirs:
            datastore = os.path.join(root, db_path)
            if os.path.isfile(datastore):
                filename = datastore
                break

    if filename is None:
        raise ValueError("No example data store found for {} in example dirs {}"
                         .format(relpath, example_dirs))

    return filename


class DataRange(object):
    """
    Express a range some data must be within and provide parsing utility functions.

    By default, a DataRange is min inclusive and max exclusive.
    """

    def __init__(self, min=None, max=None, min_inclusive=True, max_inclusive=False):
        """
        Initialize DataRange with necessary info.

        :params min: number that scalar is >= or >. None for negative
                          infinity
        :params min_inclusive: True if min inclusive (>=), False for
                                > only
        :params max: number that scalar is < or <=. None for positive
                infinity
        :params max_inclusive: True if max inclusive (<=), False for
                                 < only
        """
        self.min = min
        self.min_inclusive = min_inclusive
        self.max = max
        self.max_inclusive = max_inclusive
        if self.min and self.max:
            self.validate_and_standardize_range()

    def __repr__(self):
        """Return a comprehensive (debug) representation of a DataRange."""
        return ('DataRange <min={}, min_inclusive={}, max={}, '
                'max_inclusive={}>'.format(self.min,
                                           self.min_inclusive,
                                           self.max,
                                           self.max_inclusive))

    def __str__(self):
        """Return a DataRange in range format ({x, y} [x, y}, {,y], etc.)."""
        return "{}{}, {}{}".format(("[" if self.min_inclusive else "("),
                                   (self.min if self.min is not None else "-inf"),
                                   (self.max if self.max is not None else "inf"),
                                   ("]" if self.max_inclusive else ")"))

    def __eq__(self, other):
        """
        Check whether two DataRanges are equivalent.

        :param other: The object to compare against.
        """
        return(isinstance(other, DataRange)
               and self.__dict__ == other.__dict__)

    def set_min(self, min_range):
        """
        Parse the minimum half of a range, ex: the "[4" in "[4,2]".

        Sets the DataRange's minimum portion to be inclusive/not depending on
        the arg's min paren/bracket,  and its min number to be whatever's
        provided by the arg.

        :param str min_range: a string of the form '<range_end>[value]',
                               ex: '[4' or '(', that represents the min side
                               of a numerical range
        """
        LOGGER.debug('Setting min of range: {}'.format(min_range))
        if not min_range[0] in ['(', '[']:
            raise ValueError("Bad inclusiveness specifier for range: {}",
                             format(min_range[0]))
        if len(min_range) > 1:
            self.min_inclusive = min_range[0] is '['

            # We can take strings, but here we're already taking a string.
            # Thus we need to do a check: '"4"]' is passing us a string, but
            # '4]', despite being a string itself, is passing us an int
            min_arg = min_range[1:]
            try:
                self.min = float(min_arg)
            except ValueError:
                self.min = min_arg.strip("'").strip('"')
            self.validate_and_standardize_range()

        else:
            # None represents negative infinity in range notation.
            self.min = None
            # Negative infinity can't be inclusive.
            self.min_inclusive = False

    def set_max(self, max_range):
        """
        Parse the maximum half of a range, ex: the "2]" in "[4,2]".

        Sets the DataRange's maximum portion to be inclusive/not depending on
        the arg's max paren/bracket,  and its max number to be whatever's
        provided by the arg.

        :param str max_range: a string of the form '[value]<range_end>',
                                ex: '4)' or ']', that represents the max side
                                of a numerical range
        """
        LOGGER.debug('Setting max of range: {}'.format(max_range))
        if not max_range[-1] in [')', ']']:
            raise ValueError("Bad inclusiveness specifier for range: {}",
                             format(max_range[-1]))
        if len(max_range) > 1:
            self.max_inclusive = max_range[-1] is ']'
            # We can take strings, but here we're already taking a string.
            # Thus we need to do a check: '"4"]' is passing us a string, but
            # '4]', despite being a string itself, is passing us an int
            max_arg = max_range[:-1]
            try:
                self.max = float(max_arg)
            except ValueError:
                self.max = max_arg.strip("'").strip('"')
            self.validate_and_standardize_range()
        else:
            # None represents positive infinity in range notation.
            self.max = None
            # Positive infinity can't be inclusive
            self.max_inclusive = False

    def set_equal(self, val):
        """
        Set a DataRange equal to a single value while preserving notation.

        This is provided for the convenience case of testing exact equivalence
        (=5), allowing the user to just write =5 instead of =[5:5].

        :param val: The value (string or number) to set the DataRange to.
        """
        LOGGER.debug('Setting range equal to: {}'.format(val))
        self.min = val
        self.max = val
        self.min_inclusive = True
        self.max_inclusive = True
        self.validate_and_standardize_range()

    def validate_and_standardize_range(self):
        """
        Ensure that members of a range are set to correct types.

        Raise exceptions if not.

        :raises ValueError: if given an impossible range, ex: [3,2]
        :raises TypeError: if the range has a component of the wrong type,
                           ex [2,[-1,-2]], or mismatched types ex [4, "4"]
        """
        LOGGER.debug('Validating and standardizing range of: {}'.format(self))
        try:
            # Case 1: min or max is number. Other must be number or None.
            if isinstance(self.min, Number) or isinstance(self.max, Number):
                self.min = float(self.min) if self.min is not None else None
                self.max = float(self.max) if self.max is not None else None
            # Case 2: neither min nor max is number. Both must be None or string
            elif (not isinstance(self.min, (str, type(None))
                  or not isinstance(self.max, (str, type(None))))):
                raise ValueError
            # Note that both being None is a special case, since then we don't
            # know if what we're ultimately looking for is a number or string.
        except ValueError:
            msg = ("Bad type for portion of range: {}".format(self))
            LOGGER.error(msg)
            raise TypeError(msg)  # TypeError, as ValueError is a bit broad

        if self.min is not None:
            min_gt_max = self.max is not None and self.min > self.max
            max_eq_min = self.max is not None and self.min == self.max
            impossible_range = max_eq_min and not (self.min_inclusive and self.max_inclusive)
            if min_gt_max or impossible_range:
                msg = ("Bad range for data, min must be <= max: {}"
                       .format(self))
                LOGGER.error(msg)
                raise ValueError(msg)


class ScalarRange(object):
    """Store scalar name and range, and provide parsing utility functions."""

    def __init__(self, name, min=None, min_inclusive=False,
                 max=None, max_inclusive=False):
        """
        Initialize ScalarRange with necessary info.

        :params name: name of the scalar value (ex: velocity, density)
        :params min: number that scalar is >= or >. None for negative
                          infinity
        :params min_inclusive: True if min inclusive (>=), False for
                                > only
        :params max: number that scalar is < or <=. None for positive
                infinity
        :params max_inclusive: True if max inclusive (<=), False for
                                 < only
        """
        self.name = name
        self.min = min
        self.min_inclusive = min_inclusive
        self.max = max
        self.max_inclusive = max_inclusive

    def __repr__(self):
        """Return a comprehensive (debug) representation of a ScalarRange."""
        return ('ScalarRange <name={}, min={}, min_inclusive={}, max={}, '
                'max_inclusive={}>'.format(self.name,
                                           self.min,
                                           self.min_inclusive,
                                           self.max,
                                           self.max_inclusive))

    def __str__(self):
        """Return a ScalarRange in range format ({x, y} [x, y}, {,y], etc.)."""
        return "{} = {}{}, {}{}".format(self.name,
                                        ("[" if self.min_inclusive else "("),
                                        (self.min if self.min
                                         is not None else "-inf"),
                                        (self.max if self.max
                                         is not None else "inf"),
                                        ("]" if self.max_inclusive else ")")
                                        )

    def set_min(self, left_range):
        """
        Parse the left (min) half of a range.

        Sets the ScalarRange's left portion to be inclusive/not depending on
        the arg's left paren/bracket,  and its left number to be whatever's
        provided by the arg.

        :param str left_range: a string of the form '<range_end>[number]',
                               ex: '[4', that represents the left side of a
                               numerical range
        """
        LOGGER.debug('Setting min of range: {}'.format(left_range))
        if len(left_range) > 1:
            self.min_inclusive = left_range[0] is '['
            self.min = left_range[1:]
        else:
            # None represents negative infinity in range notation.
            self.min = None
            # Negative infinity can't be inclusive.
            self.min_inclusive = False

    def set_max(self, right_range):
        """
        Parse the right (max) half of a range.

        Sets the ScalarRange's right portion to be inclusive/not depending on
        the arg's right paren/bracket,  and its right number to be whatever's
        provided by the arg.

        :param str right_range: a string of the form '[number]<range_end>',
                                ex: '}', that represents the right side of a
                                numerical range
        """
        LOGGER.debug('Setting max of range: {}'.format(right_range))
        if len(right_range) > 1:
            self.max_inclusive = right_range[-1] is ']'
            self.max = right_range[:-1]
        else:
            # None represents positive infinity in range notation.
            self.max = None
            # Positive infinity can't be inclusive
            self.max_inclusive = False

    def set_equal(self, num):
        """
        Set a ScalarRange equal to a single number while preserving notation.

        This is provided for the convenience case of testing exact equivalence
        (=5), allowing the user to just write =5 instead of =[5:5].
        """
        LOGGER.debug('Setting range equal to: {}'.format(num))
        self.min = num
        self.max = num
        self.min_inclusive = True
        self.max_inclusive = True

    def validate_and_standardize_range(self):
        """
        Ensure that members of a range are set to correct types.

        Raise exceptions if not.

        :raises ValueError: if given an impossible range, ex: [3,2]
        :raises TypeError: if the range has a component of the wrong type,
                           ex [2,"str"]
        """
        LOGGER.debug('Validating and standardizing range of: {}'.format(self))
        try:
            self.min = float(
                self.min) if self.min is not None else None
            self.max = float(
                self.max) if self.max is not None else None
            self.min_inclusive = bool(self.min_inclusive)
            self.max_inclusive = bool(self.max_inclusive)
        except ValueError:
            msg = ("Bad type for portion of  \'{}\' range".format(
                   self.name))
            LOGGER.error(msg)
            raise TypeError(msg)  # TypeError as ValueError is a bit broad
        if self.min is not None:
            min_gt_max = self.max is not None and self.min > self.max
            max_eq_min = self.max is not None and self.min == self.max
            impossible_range = max_eq_min and not (self.min_inclusive and self.max_inclusive)
            if min_gt_max or impossible_range:
                msg = ("Bad range for scalar  \'{}\': min must be <= max"
                       .format(self.name))
                LOGGER.error(msg)
                raise ValueError(msg)
