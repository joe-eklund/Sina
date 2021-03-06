#!/bin/python
"""Test a Sina backend."""

import os
import unittest
import json
import csv
import logging
from collections import OrderedDict
import types

import six

# Disable pylint check due to its issue with virtual environments
from mock import patch  # pylint: disable=import-error

from sina.utils import (DataRange, import_json, export, _export_csv, has_all,
                        has_any, has_only)
from sina.model import Run, Record, Relationship

LOGGER = logging.getLogger(__name__)
TARGET = None


# Disable pylint invalid-name due to significant number of tests with names
# exceeding the 30 character limit
# pylint: disable=invalid-name

def create_daos(class_):
    """
    Create DAOs for the specified class.

    :param class_: Backend class
    """
    class_.factory = class_.create_dao_factory()
    class_.record_dao = class_.factory.create_record_dao()
    class_.run_dao = class_.factory.create_run_dao()
    class_.relationship_dao = class_.factory.create_relationship_dao()


def populate_database_with_data(record_dao):
    """
    Add test data to a database in a backend-independent way.

    :param record_dao: The RecordDAO used to insert records into a database.
    """
    spam_record = Record(id="spam", type="run")
    spam_record["application"] = "breakfast_maker"
    spam_record["user"] = "Bob"
    spam_record["version"] = "1.4.0"
    spam_record.data["spam_scal"] = {"value": 10, "units": "pigs", "tags": ["hammy"]}
    spam_record.data["spam_scal_2"] = {"value": 200}
    spam_record.data["val_data"] = {"value": "runny", "tags": ["edible"]}
    spam_record.data["val_data_2"] = {"value": "double yolks"}
    spam_record.files = [{"uri": "beep.wav"},
                         {"uri": "beep.pong"}]

    spam_record_2 = Record(id="spam2", type="run")
    spam_record_2.data["spam_scal"] = {"value": 10.99999}
    spam_record_2.files = [{"uri": "beep/png"}]

    spam_record_3 = Record(id="spam3", type="foo")
    spam_record_3.data["spam_scal"] = {"value": 10.5}
    spam_record_3.data["spam_scal_2"] = {"value": 10.5}
    spam_record_3.data["val_data"] = {"value": "chewy", "tags": ["edible"]}
    spam_record_3.data["val_data_2"] = {"value": "double yolks"}
    spam_record_3.files = [{"uri": "beeq.png"}]

    spam_record_4 = Record(id="spam4", type="bar")
    spam_record_4.data["val_data_2"] = {"value": "double yolks"}
    spam_record_4.files = [{"uri": "beep.png"}]

    spam_record_5 = Record(id="spam5", type="run")
    spam_record_5.data["spam_scal_3"] = {"value": 46}
    spam_record_5.data["val_data_3"] = {"value": "sugar"}
    spam_record_5.data["val_data_list_1"] = {"value": [0, 9.3]}
    spam_record_5.data["val_data_list_2"] = {"value": ['eggs', 'pancake']}
    spam_record_5.files = [{"uri": "beep.wav",
                            "tags": ["output", "eggs"],
                            "mimetype": 'audio/wav'}]

    spam_record_6 = Record(id="spam6", type="spamrec")
    spam_record_6.data["val_data_3"] = {"value": "syrup"}
    spam_record_6.data["val_data_list_1"] = {"value": [8, 20]}
    spam_record_6.data["val_data_list_2"] = {"value": ['eggs', 'yellow']}

    egg_record = Record(id="eggs", type="eggrec")
    egg_record.data["eggs_scal"] = {"value": 0}

    record_dao.insert_many([spam_record, spam_record_2, spam_record_3,
                            spam_record_4, spam_record_5, spam_record_6,
                            egg_record])


def remove_file(filename):
    """
    Remove the specified file if it exists.

    :param filename: Name of the file to be removed
    """
    try:
        os.remove(filename)
    except OSError:
        pass


class TestSetup(unittest.TestCase):
    """
    Unit tests that involve setting up pre-data-handling.

    Anything involving creating and closing connections, DAOFactories,
    or data handlers goes here.
    """

    # This tells nose not to run these tests.
    # The runnable versions of the tests are provided in backend_specific files (sql_test.py, etc)
    __test__ = False

    def setUp(self):
        """
        Set up info needed for each Setup test.

        Attributes must be set to appropriate (backend-specific) values by
        child.
        """
        self.backend = None
        self.test_db_dest = None
        raise NotImplementedError

    # DAOFactory
    def test_factory_instantiate(self):
        """Test to ensure DAOFactories can be created.

        Builds two factories: one in memory, one as a file. Test passes if no
        errors are thrown and database file is created.
        """
        factory = self.create_dao_factory()
        self.assertIsInstance(factory, self.backend.DAOFactory)
        self.assertFalse(os.path.isfile(self.test_db_dest))

    def create_dao_factory(self):
        """Create the DAO to run Setup tests. Must be implemented by child."""
        raise NotImplementedError


class TestModify(unittest.TestCase):
    """
    Unit tests that modify the database.

    Things like deletion and insertion go here. Each test is responsible for
    creating its own factory connection due to the database being wiped after
    each test.
    """

    __test__ = False

    def setUp(self):
        """
        Set up info needed for each Modify test.

        Attributes must be set to appropriate (backend-specific) values by
        child.

        param test_db_dest: The database tests will target for modification.
        """
        self.test_db_dest = None
        raise NotImplementedError

    def create_dao_factory(self, test_db_dest=None):
        """
        Create the DAO to run Modify tests.

        Must be implemented by child, likely via its mixin class (ex: SQLMixin).

        param test_db_dest: The database that the DAOFactory should target.
        """
        raise NotImplementedError

    def test_recorddao_insert_retrieve(self):
        """Test that RecordDAO is inserting and getting correctly."""
        record_dao = self.create_dao_factory().create_record_dao()
        rec = Record(id="spam", type="eggs",
                     data={"eggs": {"value": 12, "units": None, "tags": ["runny"]}},
                     files=[{"uri": "eggs.brek", "mimetype": "egg", "tags": ["fried"]}],
                     user_defined={})
        record_dao.insert(rec)
        returned_record = record_dao.get("spam")
        # Test one definition of Record equivalence.
        # Done instead of __dict__ to make it clearer what part fails (if any)
        self.assertEqual(returned_record.id, rec.id)
        self.assertEqual(returned_record.type, rec.type)
        self.assertEqual(returned_record.data, rec.data)
        self.assertEqual(returned_record.files, rec.files)
        self.assertEqual(returned_record.user_defined, rec.user_defined)

    def test_recorddao_delete_one(self):
        """Test that RecordDAO is deleting correctly."""
        record_dao = self.create_dao_factory(test_db_dest=self.test_db_dest).create_record_dao()
        record_dao.insert(Record(id="rec_1", type="sample"))
        record_dao.delete("rec_1")
        self.assertEqual(list(record_dao.get_all_of_type("sample")), [])

    def test_recorddao_delete_data_cascade(self):
        """Test that deletion of a Record correctly cascades to data and files."""
        factory = self.create_dao_factory(test_db_dest=self.test_db_dest)
        record_dao = factory.create_record_dao()
        data = {"eggs": {"value": 12, "tags": ["breakfast"]},
                "flavor": {"value": "tasty"}}
        files = [{"uri": "justheretoexist.png"}]
        record_dao.insert(Record(id="rec_1", type="sample", data=data, files=files))
        record_dao.delete("rec_1")
        # Make sure the data, raw, files, and relationships were deleted as well
        dead_data = record_dao.get_data_for_records(id_list=["rec_1"],
                                                    data_list=["eggs", "flavor"])
        self.assertEqual(dead_data, {})
        dead_files = list(record_dao.get_given_document_uri("justheretoexist.png",
                                                            ids_only=True))
        self.assertEqual(dead_files, [])

    def test_recorddao_delete_one_with_relationship(self):
        """Test that RecordDAO deletions include relationships."""
        factory = self.create_dao_factory(test_db_dest=self.test_db_dest)
        record_dao = factory.create_record_dao()
        relationship_dao = factory.create_relationship_dao()
        record_1 = Record(id="rec_1", type="sample")
        record_2 = Record(id="rec_2", type="sample")
        record_dao.insert_many([record_1, record_2])
        relationship_dao.insert(subject_id="rec_1", object_id="rec_2", predicate="dupes")
        record_dao.delete("rec_1")
        # Make sure the relationship was deleted
        self.assertFalse(relationship_dao.get(subject_id="rec_1"))
        # rec_2 should not be deleted
        remaining_records = list(record_dao.get_all_of_type("sample", ids_only=True))
        self.assertEqual(remaining_records, ["rec_2"])

    def test_recorddao_delete_many(self):
        """Test that RecordDAO can delete many at once."""
        factory = self.create_dao_factory(test_db_dest=self.test_db_dest)
        record_dao = factory.create_record_dao()
        relationship_dao = factory.create_relationship_dao()
        record_1 = Record(id="rec_1", type="sample")
        record_2 = Record(id="rec_2", type="sample")
        record_3 = Record(id="rec_3", type="sample")
        record_4 = Record(id="rec_4", type="sample")
        all_ids = ["rec_1", "rec_2", "rec_3", "rec_4"]
        record_dao.insert_many([record_1, record_2, record_3, record_4])
        relationship_dao.insert(subject_id="rec_1", object_id="rec_2", predicate="dupes")
        relationship_dao.insert(subject_id="rec_2", object_id="rec_2", predicate="is")
        relationship_dao.insert(subject_id="rec_3", object_id="rec_4", predicate="dupes")
        relationship_dao.insert(subject_id="rec_4", object_id="rec_4", predicate="is")
        # Delete several
        record_dao.delete_many(["rec_1", "rec_2", "rec_3"])
        remaining_records = list(record_dao.get_all_of_type("sample", ids_only=True))
        self.assertEqual(remaining_records, ["rec_4"])

        # Make sure expected data entries were deleted as well (acts as cascade test)
        for_all = record_dao.get_data_for_records(id_list=all_ids,
                                                  data_list=["eggs", "flavor"])
        for_one = record_dao.get_data_for_records(id_list=["rec_4"],
                                                  data_list=["eggs", "flavor"])
        self.assertEqual(for_all, for_one)

        # Make sure expected Relationships were deleted
        self.assertFalse(relationship_dao.get(object_id="rec_2"))
        self.assertFalse(relationship_dao.get(subject_id="rec_3"))
        self.assertEqual(len(relationship_dao.get(object_id="rec_4")), 1)

    # RelationshipDAO
    # pylint: disable=fixme
    # TODO: There's no delete method for Relationships. SIBO-781
    def test_relationshipdao_insert_simple_retrieve(self):
        """Test that RelationshipDAO is inserting and getting correctly."""
        relationship_dao = self.create_dao_factory().create_relationship_dao()
        relationship = Relationship(subject_id="spam", object_id="eggs", predicate="loves")
        relationship_dao.insert(relationship)
        subj = relationship_dao.get(subject_id=relationship.subject_id)
        pred = relationship_dao.get(predicate=relationship.predicate)
        for relationship_list in (subj, pred):
            result = relationship_list[0]
            # Testing one definition of "equality" between Relationships.
            self.assertEqual(result.subject_id, relationship.subject_id)
            self.assertEqual(result.object_id, relationship.object_id)
            self.assertEqual(result.predicate, relationship.predicate)

    def test_relationshipdao_insert_compound_retrieve(self):
        """Test that RelationshipDAO's multi-criteria getter is working correctly."""
        relationship_dao = self.create_dao_factory().create_relationship_dao()
        relationship = Relationship(subject_id="spam", object_id="eggs", predicate="loves")
        relationship_dao.insert(relationship)
        obj_pred = relationship_dao.get(object_id=relationship.object_id,
                                        predicate=relationship.predicate)
        full = relationship_dao.get(subject_id=relationship.subject_id,
                                    object_id=relationship.object_id,
                                    predicate=relationship.predicate)
        for relationship_list in (obj_pred, full):
            result = relationship_list[0]
            self.assertEqual(result.subject_id, relationship.subject_id)
            self.assertEqual(result.object_id, relationship.object_id)
            self.assertEqual(result.predicate, relationship.predicate)

    def test_relationshipdao_bad_insert(self):
        """Test that the RelationshipDAO refuses to insert malformed relationships."""
        relationship_dao = self.create_dao_factory().create_relationship_dao()
        with self.assertRaises(ValueError) as context:
            relationship_dao.insert(subject_id="spam", object_id="eggs")
        self.assertIn('Must supply either', str(context.exception))

    # RunDAO
    def test_runddao_insert_retrieve(self):
        """Test that RunDAO is inserting and getting correctly."""
        run_dao = self.create_dao_factory().create_run_dao()
        run = Run(id="spam", version="1.2.3",
                  application="bar", user="bep",
                  user_defined={"boop": "bep"},
                  data={"scalar-strings": {"value": ["red", "green", "blue"], "units": None},
                        "scalar-numbers": {"value": [1, 2, 3], "units": "m"},
                        "foo": {"value": 12, "units": None, "tags": ["in", "on"]},
                        "bar": {"value": "1", "units": None}},)
        run_dao.insert(run)
        returned_run = run_dao.get("spam")
        # Testing one definition of "equality" between Runs.
        # Used instead of __dict__ to make it easier to tell what part(s) fail
        self.assertEqual(returned_run.id, run.id)
        self.assertEqual(returned_run.raw, run.raw)
        self.assertEqual(returned_run.application, run.application)
        self.assertEqual(returned_run.user, run.user)
        self.assertEqual(returned_run.user_defined, run.user_defined)
        self.assertEqual(returned_run.version, run.version)
        self.assertEqual(returned_run.data, run.data)

    def test_rundao_delete(self):
        """Test that RunDAO is deleting correctly."""
        factory = self.create_dao_factory(test_db_dest=self.test_db_dest)
        run_dao = factory.create_run_dao()
        relationship_dao = factory.create_relationship_dao()
        run_1 = Run(id="run_1", application="eggs")
        run_2 = Run(id="run_2", application="spam")
        run_dao.insert_many([run_1, run_2])
        relationship_dao.insert(subject_id="run_1", object_id="run_2", predicate="dupes")
        # Ensure there's two entries in the Run table
        self.assertEqual(len(list(run_dao.get_all(ids_only=True))), 2)
        # Delete one
        run_dao.delete("run_1")
        # Now there should only be one Run left
        self.assertEqual(len(list(run_dao.get_all(ids_only=True))), 1)
        # The Relationship should be removed as well
        self.assertFalse(relationship_dao.get(subject_id="rec_1"))


# Disable the pylint check if and until the team decides to refactor the code
class TestQuery(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """
    Unit tests that specifically deal with queries.

    These tests do not modify the database.
    """

    __test__ = False

    @classmethod
    def setUpClass(cls):
        """
        Initialize variables shared between Query tests.

        Class method to avoid it being re-run per test. Attributes must be set
        to appropriate (backend-specific) values by child.

        :param record_dao: A RecordDAO to perform queries.
        :param run_dao: A RunDAO to perform queries.
        """
        cls.record_dao = None
        cls.run_dao = None
        raise NotImplementedError

    # Due to the length of this section of tests, tests dealing with specific
    # methods are separated by headers.
    # ###################### get_given_document_uri ##########################
    def test_recorddao_uri_no_wildcards(self):
        """Test that RecordDAO is retrieving based on full uris correctly."""
        exact_match = self.record_dao.get_given_document_uri(uri="beep.png", ids_only=True)
        self.assertEqual(len(list(exact_match)), 1)

    def test_recorddao_uri_no_match(self):
        """Test that the RecordDAO uri query is retrieving no Records when there's no matches."""
        exact_match = self.record_dao.get_given_document_uri(uri="idontexist.png", ids_only=True)
        self.assertEqual(len(list(exact_match)), 0)

    def test_recorddao_uri_returns_generator(self):
        """Test that the uri-query method returns a generator."""
        exact_match = self.record_dao.get_given_document_uri(uri="beep.png", ids_only=True)
        self.assertIsInstance(exact_match, types.GeneratorType,
                              "Method must return a generator.")

    def test_recorddao_uri_one_wildcard(self):
        """Test that RecordDAO is retrieving based on a wildcard-containing uri correctly."""
        end_wildcard = self.record_dao.get_given_document_uri(uri="beep.%", ids_only=True)
        # Note that we're expecting 3 even though there's 4 matches.
        # That's because id "beep" matches twice, but we don't repeat matches.
        self.assertEqual(len(list(end_wildcard)), 3)
        mid_wildcard = self.record_dao.get_given_document_uri(uri="beep%png")
        self.assertEqual(len(list(mid_wildcard)), 2)
        first_wildcard = self.record_dao.get_given_document_uri(uri="%png")
        self.assertEqual(len(list(first_wildcard)), 3)

    def test_recorddao_uri_many_wildcards(self):
        """Test that RecordDAO is retrieving based on many wildcards correctly."""
        multi_wildcard = self.record_dao.get_given_document_uri(uri="%.%")
        self.assertEqual(len(list(multi_wildcard)), 4)
        ids_only = list(self.record_dao.get_given_document_uri(uri="%.%", ids_only=True))
        self.assertEqual(len(ids_only), 4)
        six.assertCountEqual(self, ids_only, ["spam", "spam5", "spam3", "spam4"])

    def test_recorddao_uri_full_wildcard(self):
        """Ensure that a uri=% (wildcard) uri query matches all Records with files."""
        all_wildcard = self.record_dao.get_given_document_uri(uri="%")
        self.assertEqual(len(list(all_wildcard)), 5)

    # ########################### basic data_query ##########################
    def test_recorddao_scalar_datum_query(self):
        """Test that the RecordDAO data query is retrieving based on one scalar correctly."""
        just_right_range = DataRange(min=0, max=300, max_inclusive=True)
        just_right = self.record_dao.data_query(spam_scal=just_right_range)
        self.assertEqual(len(list(just_right)), 3)

    def test_recorddao_data_query_returns_generator(self):
        """Test that the data-query method returns a generator."""
        too_big_range = DataRange(max=9, max_inclusive=True)
        too_big = self.record_dao.data_query(spam_scal=too_big_range)
        self.assertIsInstance(too_big, types.GeneratorType,
                              "Method must return generator.")

    def test_recorddao_scalar_datum_query_no_match(self):
        """Test that the RecordDAO data query is retrieving no Records when there's no matches."""
        too_small_range = DataRange(min=10.99999, min_inclusive=False)
        too_small = self.record_dao.data_query(spam_scal=too_small_range)
        self.assertFalse(list(too_small))
        nonexistant_scalar = self.record_dao.data_query(nonexistant_scalar=DataRange(-999, 0))
        self.assertFalse(list(nonexistant_scalar))

    def test_recorddao_many_scalar_data_query(self):
        """Test that RecordDAO's data query is retrieving on multiple scalars correctly."""
        spam_and_spam_3 = DataRange(min=10)
        one = self.record_dao.data_query(spam_scal=spam_and_spam_3,
                                         spam_scal_2=10.5)  # Matches spam_3 only
        self.assertEqual(len(list(one)), 1)
        none = self.record_dao.data_query(spam_scal=spam_and_spam_3,
                                          nonexistant=10101010)
        self.assertFalse(list(none))

    def test_recorddao_string_datum_query(self):
        """Test that the RecordDAO data query is retrieving based on one string correctly."""
        just_right_range = DataRange(min="astounding", max="runny", max_inclusive=True)
        just_right = self.record_dao.data_query(val_data=just_right_range)
        just_right_list = list(just_right)
        self.assertEqual(len(just_right_list), 2)
        six.assertCountEqual(self, just_right_list, ["spam", "spam3"])

    def test_recorddao_string_datum_query_no_match(self):
        """
        Test that the RecordDAO data query is retrieving no Records when there's no matches.

        String data edition.
        """
        too_big_range = DataRange(max="awesome", max_inclusive=True)
        too_big = self.record_dao.data_query(val_data=too_big_range)
        self.assertFalse(list(too_big))
        nonexistant_string = self.record_dao.data_query(nonexistant_string="narf")
        self.assertFalse(list(nonexistant_string))

    def test_recorddao_many_string_data_query(self):
        """Test that RecordDAO's data query is retrieving on multiple strings correctly."""
        one = self.record_dao.data_query(val_data=DataRange("runny"),  # Matches 1 only
                                         val_data_2="double yolks")  # Matches 1 and 3
        self.assertEqual(list(one), ["spam"])

    def test_recorddao_data_query_strings_and_records(self):
        """Test that the RecordDAO is retrieving on scalars AND strings correctly."""
        just_3 = self.record_dao.data_query(spam_scal=DataRange(10.1, 400),  # 2 and 3
                                            val_data_2="double yolks")  # 1, 3, and 4
        self.assertEqual(list(just_3), ["spam3"])

    # ###################### data_query list queries ########################
    def test_recorddao_data_query_scalar_list_has_all(self):
        """Test that the RecordDAO is retrieving on a has_all list of scalars."""
        just_5_and_6 = list(self.record_dao.data_query(
            val_data_list_1=has_all(DataRange(-10, 8.5), DataRange(8.9, 25))))  # 5 & 6
        self.assertEqual(len(just_5_and_6), 2)
        self.assertIn("spam5", just_5_and_6)
        self.assertIn("spam6", just_5_and_6)

    def test_recorddao_data_query_scalar_list_has_any(self):
        """Test that the RecordDAO is retrieving on a has_any list of scalars."""
        just_5_and_6 = list(self.record_dao.data_query(
            val_data_list_1=has_any(DataRange(-1, 1), DataRange(7.5, 9))))  # 5 & 6
        self.assertEqual(len(just_5_and_6), 2)
        self.assertIn("spam5", just_5_and_6)
        self.assertIn("spam6", just_5_and_6)

    def test_recorddao_data_query_scalar_list_has_only(self):
        """Test that the RecordDAO is retrieving on a has_only list of scalars."""
        just_5 = list(self.record_dao.data_query(
            val_data_list_1=has_only(DataRange(-1, 1), DataRange(7.5, 10))))  # 5 only
        self.assertEqual(len(just_5), 1)
        self.assertIn("spam5", just_5)

    def test_recorddao_data_query_has_all_mixed(self):
        """
        Test that the RecordDAO is retrieving on mixed data types for has_all.

        Test that we can mix searching on scalars and lists of scalars.
        """
        just_5 = list(self.record_dao.data_query(
            val_data_list_1=has_all(DataRange(-10, 8.5), DataRange(8.9, 25)),  # 5 & 6
            spam_scal_3=DataRange(0, 50)))  # 5 only
        self.assertEqual(len(just_5), 1)
        self.assertEqual(just_5[0], "spam5")

    def test_recorddao_data_query_has_any_mixed(self):
        """
        Test that the RecordDAO is retrieving on mixed data types for has_any.

        Test that we can mix searching on scalars and lists of scalars.
        """
        just_5 = list(self.record_dao.data_query(
            val_data_list_1=has_any(DataRange(-1, 1), DataRange(7.5, 9)),  # 5 & 6
            spam_scal_3=DataRange(0, 50)))  # 5 only
        self.assertEqual(len(just_5), 1)
        self.assertEqual(just_5[0], "spam5")

    def test_recorddao_data_query_has_only_mixed(self):
        """
        Test that the RecordDAO is retrieving on mixed data types for has_only.

        Test that we can mix searching on scalars and lists of scalars.
        """
        just_5 = list(self.record_dao.data_query(
            val_data_list_1=has_only(DataRange(-1, 1), DataRange(7.5, 21)),  # 5 & 6
            spam_scal_3=DataRange(0, 50)))  # 5 only
        self.assertEqual(len(just_5), 1)
        self.assertEqual(just_5[0], "spam5")

    def test_recorddao_data_query_string_list_has_all(self):
        """Test that the RecordDAO is retrieving on a has_all list of strings."""
        just_5_and_6 = list(self.record_dao.data_query(
            val_data_list_2=has_all('eggs', DataRange('o', 'z'))))  # 5 & 6
        self.assertEqual(len(just_5_and_6), 2)
        self.assertIn("spam5", just_5_and_6)
        self.assertIn("spam6", just_5_and_6)

    def test_recorddao_data_query_string_list_has_any(self):
        """Test that the RecordDAO is retrieving on a has_any list of strings."""
        just_5_and_6 = list(self.record_dao.data_query(
            val_data_list_2=has_any('yellow', 'pancake')))  # 5 & 6
        self.assertEqual(len(just_5_and_6), 2)
        self.assertIn("spam5", just_5_and_6)
        self.assertIn("spam6", just_5_and_6)

    def test_recorddao_data_query_string_list_has_only(self):
        """Test that the RecordDAO is retrieving on a has_only list of strings."""
        just_5 = list(self.record_dao.data_query(
            val_data_list_2=has_only('eggs', 'pancake')))  # 5 only
        self.assertEqual(len(just_5), 1)
        self.assertIn("spam5", just_5)

    def test_recorddao_data_query_mixed_list_criteria(self):
        """
        Test that the RecordDAO is retrieving on mixed data criteria.

        Test that we can mix searching on strings, lists of strings, and lists of scalars.
        """
        just_6 = list(self.record_dao.data_query(
            val_data_list_2=has_all('eggs', DataRange('o', 'z')),  # 5 & 6
            val_data_list_1=has_any(0, 8),  # 5 & 6
            val_data_3='syrup'))  # 6 only
        self.assertEqual(len(just_6), 1)
        self.assertEqual(just_6[0], "spam6")

    def test_recorddao_data_query_all_list_criteria(self):
        """
        Test that the RecordDAO is retrieving on mixed data types.

        Test that we can mix searching on strings, scalars, lists of strings,
        and lists of scalars, using has_all, has_any, and has_only
        """
        no_match = list(self.record_dao.data_query(
            val_data_list_1=has_any(DataRange(-10, 8.5), DataRange(8.9, 25)),  # 5 & 6
            spam_scal_3=DataRange(0, 50),  # 5 only
            val_data_list_2=has_all('eggs', DataRange('o', 'z')),  # 5 & 6
            val_data_3=has_only(0, 9.3)))  # 6 only
        self.assertFalse(no_match)

        just_5 = list(self.record_dao.data_query(
            val_data_list_1=has_all(DataRange(-10, 8.5), DataRange(8.9, 25)),  # 5 & 6
            spam_scal_3=DataRange(0, 50),  # 5 only
            val_data_list_2=has_all('eggs', DataRange('o', 'z')),  # 5 & 6
            val_data_3='sugar'))  # 5 only

        self.assertEqual(len(just_5), 1)
        self.assertEqual(just_5[0], "spam5")

    # ####################### data_query for Runs #########################
    def test_rundao_get_by_scalars(self):
        """
        Test ability to find Runs by scalars.

        The current version inherits from RecordDAO and does only a little
        extra processing, and most of that via convert_record_to_run(). We're
        mostly making sure nothing gets lost between those two.
        """
        multi_scalar = list(self.run_dao.data_query(spam_scal=DataRange(-500, 500)))
        six.assertCountEqual(self, multi_scalar, ["spam", "spam2"])

    # ######################### get_all_of_type ###########################
    def test_recorddao_type(self):
        """Test the RecordDAO is retrieving based on type correctly."""
        get_one = list(self.record_dao.get_all_of_type("bar"))
        self.assertEqual(len(get_one), 1)
        self.assertIsInstance(get_one[0], Record)
        self.assertEqual(get_one[0].id, "spam4")
        self.assertEqual(get_one[0].type, "bar")
        self.assertEqual(get_one[0].user_defined, {})

    def test_recorddao_type_none(self):
        """Test that the RecordDAO type query returns no Records when none match."""
        get_none = list(self.record_dao.get_all_of_type("butterscotch"))
        self.assertFalse(get_none)

    def test_recorddao_type_returns_generator(self):
        """Test that the RecordDAO type query returns a generator."""
        ids_only = self.record_dao.get_all_of_type("run")
        self.assertIsInstance(ids_only, types.GeneratorType,
                              "Method must return a generator.")

    def test_recorddao_type_matches_many(self):
        """Test the RecordDAO type query correctly returns multiple Records."""
        ids_only = self.record_dao.get_all_of_type("run", ids_only=True)
        six.assertCountEqual(self, list(ids_only), ["spam", "spam2", "spam5"])

    # ########################### get_files #############################
    def test_recorddao_get_files(self):
        """Test that the RecordDAO is getting files for records correctly."""
        get_one = self.record_dao.get_files(id="spam5")
        files = self.record_dao.get("spam5").files
        self.assertEqual(get_one, files)

    # ###################### get_data_for_records ########################
    def test_recorddao_get_datum_for_record(self):
        """Test that we're getting a datum for one record correctly."""
        for_one = self.record_dao.get_data_for_records(id_list=["spam"],
                                                       data_list=["spam_scal"])
        self.assertEqual(for_one["spam"]["spam_scal"],
                         {"value": 10, "units": "pigs", "tags": ["hammy"]})

    def test_recorddao_get_data_for_record(self):
        """Test that we're getting several pieces of data for one record correctly."""
        many_scalars = ["spam_scal", "eggs_scal", "val_data"]
        for_one = self.record_dao.get_data_for_records(id_list=["spam"],
                                                       data_list=many_scalars)
        six.assertCountEqual(self, for_one["spam"].keys(), ["spam_scal", "val_data"])
        self.assertEqual(for_one["spam"]["val_data"],
                         {"value": "runny", "tags": ["edible"]})

    def test_recorddao_get_data_for_records(self):
        """Test that we're getting data for many records correctly."""
        many_ids = ["spam", "spam2", "spam3"]
        many_scalars = ["spam_scal", "eggs_scal", "spam_scal_2", "val_data"]
        for_many = self.record_dao.get_data_for_records(id_list=many_ids,
                                                        data_list=many_scalars)
        six.assertCountEqual(self, for_many.keys(), ["spam", "spam2", "spam3"])
        six.assertCountEqual(self, for_many["spam3"].keys(), ["spam_scal",
                                                              "spam_scal_2",
                                                              "val_data"])
        self.assertEqual(for_many["spam3"]["val_data"]["tags"], ["edible"])

    def test_recorddao_get_no_data_for_nonexistant_records(self):
        """Test that we're not getting data for records that don't exist."""
        for_none = self.record_dao.get_data_for_records(id_list=["nope", "nada"],
                                                        data_list=["gone", "away"])
        self.assertFalse(for_none)

    # ###################### get_scalars (legacy) ########################
    def test_recorddao_get_scalars(self):
        """Test that RecordDAO is getting scalars for a record correctly (legacy method)."""
        get_one = self.record_dao.get_scalars(id="spam",
                                              scalar_names=["spam_scal"])
        self.assertEqual(len(get_one), 1)
        self.assertEqual(get_one["spam_scal"]["units"], "pigs")
        get_more = self.record_dao.get_scalars(id="spam",
                                               scalar_names=["spam_scal_2",
                                                             "spam_scal"])
        self.assertEqual(len(get_more), 2)
        self.assertEqual(get_more["spam_scal"]["tags"], ["hammy"])
        self.assertFalse(get_more["spam_scal_2"]["units"])
        self.assertFalse(get_more["spam_scal_2"]["tags"])
        get_gone = self.record_dao.get_scalars(id="spam",
                                               scalar_names=["value-1"])
        self.assertFalse(get_gone)
        get_norec = self.record_dao.get_scalars(id="wheeee",
                                                scalar_names=["value-1"])
        self.assertFalse(get_norec)


class TestImportExport(unittest.TestCase):
    """
    Unit tests that involve importing and exporting.

    If it creates or consumes a file, it goes here.
    """

    __test__ = False

    def create_dao_factory(self):
        """
        Create the DAO to run Import/Export tests.

        Must be implemented by child, likely via its mixin class (ex: SQLMixin).
        """
        raise NotImplementedError

    def setUp(self):
        """
        Set up info needed for each Import/Export test.

        Attributes must be set to appropriate (backend-specific) values by
        child.

        :param test_file_path: The path to a test file.
        """
        self.test_file_path = None
        raise NotImplementedError

    # Importing
    def test_full_import(self):
        """
        Do an import using the utils importer, making sure all data is ingested.

        Also acts as a sanity check on all DAOs.
        """
        factory = self.create_dao_factory()
        json_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 "test_files/mnoda_1.json")
        import_json(factory=factory, json_path=json_path)
        parent = factory.create_record_dao().get("parent_1")
        relation = factory.create_relationship_dao().get(object_id="child_1")
        run_factory = factory.create_run_dao()
        child = run_factory.get("child_1")
        canonical = json.load(open(json_path))
        self.assertEqual(canonical['records'][0]['type'], parent.type)
        self.assertEqual(canonical['records'][1]['application'],
                         child.application)
        child_from_uri = list(run_factory.get_given_document_uri("foo.png"))
        child_from_scalar_id = list(run_factory.data_query(scalar_1=387.6))
        full_record = run_factory.get(child_from_scalar_id[0])
        self.assertEqual(canonical['records'][1]['application'],
                         full_record.application)
        self.assertEqual(child.id, child_from_uri[0].id)
        self.assertEqual(child.id, full_record.id)
        self.assertEqual(canonical['relationships'][0]['predicate'],
                         relation[0].predicate)

    # Exporting
    @patch('sina.utils._export_csv')
    def test_export_csv_good_input_mocked(self, mock):
        """
        Test export with mocked _csv_export() and good input.

        Test export with of one scalar from sql database to a csv file. Mock
        _export_csv() so we don't actually write to file.
        """
        factory = self.create_dao_factory()
        populate_database_with_data(factory.create_record_dao())
        scalars = ['spam_scal']
        export(
            factory=factory,
            id_list=['spam_scal'],
            scalar_names=scalars,
            output_type='csv',
            output_file=self.test_file_path.name)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)
        _, kwargs = mock.call_args
        self.assertEqual(kwargs['scalar_names'][0], scalars[0])

    @patch('sina.utils._export_csv')
    def test_export_csv_bad_input_mocked(self, mock):
        """
        Test export with mocked _csv_export() and bad input.

        Test export with of one scalar from sql database to a csv file. Mock
        _export_csv() so we don't actually write to file. Bad input in this
        case is an output_type that is not supported.
        """
        factory = self.create_dao_factory()
        populate_database_with_data(factory.create_record_dao())
        scalars = ['spam_scal']
        with self.assertRaises(ValueError) as context:
            export(
                factory=factory,
                id_list=['spam'],
                scalar_names=scalars,
                output_type='joes_output_type',
                output_file=self.test_file_path.name)
        self.assertIn('Given "joes_output_type" for output_type and it must '
                      'be one of the following: csv',
                      str(context.exception))
        self.assertEqual(mock.call_count, 0)

    def test_export_one_scalar_csv_good_input(self):
        """Test export one scalar correctly to csv from a sql database."""
        factory = self.create_dao_factory()
        populate_database_with_data(factory.create_record_dao())
        export(
            factory=factory,
            id_list=['spam'],
            scalar_names=['spam_scal'],
            output_type='csv',
            output_file=self.test_file_path.name)

        with open(self.test_file_path.name, 'r') as csvfile:
            reader = csv.reader(csvfile)
            rows = [row for row in reader]
            self.assertEqual(rows[0], ['id', 'spam_scal'])
            # 10 is stored but 10.0 is retrieved due to SQL column types
            self.assertAlmostEqual(float(rows[1][1]), 10)

    def test_export_two_scalar_csv_good_input(self):
        """Test exporting two scalars & runs correctly to csv from sql."""
        factory = self.create_dao_factory()
        populate_database_with_data(factory.create_record_dao())
        export(
            factory=factory,
            id_list=['spam3', 'spam'],
            scalar_names=['spam_scal', 'spam_scal_2'],
            output_type='csv',
            output_file=self.test_file_path.name)

        with open(self.test_file_path.name, 'r') as csvfile:
            reader = csv.reader(csvfile)
            rows = [row for row in reader]
            self.assertEqual(rows[0], ['id',
                                       'spam_scal',
                                       'spam_scal_2'])
            self.assertEqual(rows[1], ['spam3',
                                       '10.5',
                                       '10.5'])
            # AlmostEqual doesn't work with lists, but we expect floats from
            # SQL, hence this workaround
            self.assertEqual(rows[2], ['spam',
                                       '10.0',
                                       '200.0'])

    def test_export_non_existent_scalar_csv(self):
        """Test export for a non existent scalar returns no scalars."""
        export(
            factory=self.create_dao_factory(),
            id_list=['child_1'],
            scalar_names=['bad-scalar'],
            output_type='csv',
            output_file=self.test_file_path.name)

        with open(self.test_file_path.name, 'r') as csvfile:
            reader = csv.reader(csvfile)
            rows = [row for row in reader]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], ['id', 'bad-scalar'])

    def test__export_csv(self):
        """Test we can write out data to csv and ensures everything expected is present."""
        # Create temp data
        scalar_names = ['fake_scalar_1', 'fake_scalar_2']
        ids = ['a_fake_id_1', 'a_fake_id_2']
        data = OrderedDict()
        data[ids[0]] = {scalar_names[0]: {'value': 123},
                        scalar_names[1]: {'value': 456}}
        data[ids[1]] = {scalar_names[0]: {'value': 0.1},
                        scalar_names[1]: {'value': -12}}
        # Write to csv file
        _export_csv(data=data,
                    scalar_names=scalar_names,
                    output_file=self.test_file_path.name)

        # Validate csv file
        with open(self.test_file_path.name, 'r') as csvfile:
            reader = csv.reader(csvfile)
            rows = [row for row in reader]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0], ['id'] + scalar_names)
            self.assertEqual(rows[1], ['a_fake_id_1', '123', '456'])
            self.assertEqual(rows[2], ['a_fake_id_2', '0.1', '-12'])
