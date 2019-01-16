"""Test the SQL portion of the DAO structure."""

import os
import unittest
import tempfile
import time
import json
import csv
import logging
import six
from collections import OrderedDict
from mock import MagicMock, patch
import types

import sina.datastores.sql as sina_sql
import sina.datastores.sql_schema as schema
from sina.utils import ScalarRange, import_json, export, _export_csv
from sina.model import Run, Record

LOGGER = logging.getLogger(__name__)


def _populate_database_with_data(session):
    """Add test scalars to a database."""
    session.add(schema.ScalarData(id="spam",
                                  name="spam_scal",
                                  value=10,
                                  units="pigs",
                                  tags='["hammy"]'))
    session.add(schema.ScalarData(id="eggs",
                                  name="eggs_scal",
                                  value=0))
    session.add(schema.ScalarData(id="spam",
                                  name="spam_scal_2",
                                  value=200))
    session.add(schema.ScalarData(id="spam2",
                                  name="spam_scal",
                                  value=10.99999))
    session.add(schema.ScalarData(id="spam3",
                                  name="spam_scal",
                                  value=10.5))
    session.add(schema.ScalarData(id="spam3",
                                  name="spam_scal_2",
                                  value=10.5))
    session.add(schema.StringData(id="spam3",
                                  name="val_data",
                                  value="runny",
                                  tags='["edible"]'))
    session.commit()


def _populate_database_with_files(session):
    """Add test documents to a database."""
    session.add(schema.Document(id="spam", uri="beep.wav"))
    session.add(schema.Document(id="spam1", uri="beep.wav", tags='["output", "eggs"]'))
    session.add(schema.Document(id="spam2", uri="beep/png"))
    session.add(schema.Document(id="spam3", uri="beeq.png"))
    session.add(schema.Document(id="spam4", uri="beep.png"))
    session.add(schema.Document(id="spam", uri="beep.pong"))
    session.commit()


class TestSQL(unittest.TestCase):
    """Unit tests for the SQL portion of the DAO."""

    def setUp(self):
        """Define a few shared variables, such as temp files."""
        self.test_db_path = './test_{}_file.temp'.format(time.time())
        self.test_file_path = tempfile.NamedTemporaryFile(
            suffix='.csv',
            delete=False,
            mode='w+b')

    def tearDown(self):
        """Remove temp files left over from test."""
        os.remove(self.test_file_path.name)

    # DAOFactory
    def test_factory_instantiate(self):
        """
        Test to ensure DAOFactories can be created.

        Builds two factories: one in memory, one as a file. Test passes if no
        errors are thrown and database file is created.
        """
        sina_sql.DAOFactory()
        self.assertFalse(os.path.isfile(self.test_db_path))
        sina_sql.DAOFactory(self.test_db_path)
        self.assertTrue(os.path.isfile(self.test_db_path))
        os.remove(self.test_db_path)

    def test_factory_production(self):
        """
        Test to ensure DAOFactory can create all required DAOs.

        Tests passes if all required DAOs are created and are of the right
        type.

        Note that, due to use of the abc module in DAOs, this test will fail
        if any of the required DAOs do not implement all required methods.
        """
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        self.assertIsInstance(record_dao, sina_sql.RecordDAO)
        relationship_dao = factory.createRelationshipDAO()
        self.assertIsInstance(relationship_dao, sina_sql.RelationshipDAO)
        run_dao = factory.createRunDAO()
        self.assertIsInstance(run_dao, sina_sql.RunDAO)

    # Importing
    def test_full_import(self):
        """
        Do an import using the utils importer (temporary).

        Acts as a sanity check on all DAOs, though again, should be temporary.
        """
        factory = sina_sql.DAOFactory()
        json_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 "test_files/mnoda_1.json")
        import_json(factory=factory, json_path=json_path)
        parent = factory.createRecordDAO().get("parent_1")
        relation = factory.createRelationshipDAO().get(object_id="child_1")
        run_factory = factory.createRunDAO()
        child = run_factory.get("child_1")
        canonical = json.load(open(json_path))
        self.assertEquals(canonical['records'][0]['type'], parent.type)
        self.assertEquals(canonical['records'][1]['application'],
                          child.application)
        child_from_uri = list(run_factory.get_given_document_uri("foo.png"))
        child_scalar = ScalarRange(name="scalar-1", min=387.6,
                                   min_inclusive=True, max=387.6,
                                   max_inclusive=True)
        child_from_scalar = list(run_factory.get_given_scalar(child_scalar))
        self.assertEquals(canonical['records'][1]['application'],
                          child.application)
        self.assertEquals(child.id, child_from_uri[0].id)
        self.assertEquals(child.id, child_from_scalar[0].id)
        self.assertEquals(canonical['relationships'][0]['predicate'],
                          relation[0].predicate)

    # Exporting
    @patch('sina.utils._export_csv')
    def test_export_csv_good_input_mocked(self, mock):
        """
        Test export with mocked _csv_export() and good input.

        Test export with of one scalar from sql database to a csv file. Mock
        _export_csv() so we don't actually write to file.
        """
        factory = sina_sql.DAOFactory()
        _populate_database_with_data(factory.session)
        scalars = ['spam_scal']
        export(
            factory=factory,
            id_list=['spam_scal'],
            scalar_names=scalars,
            output_type='csv',
            output_file=self.test_file_path.name)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)
        args, kwargs = mock.call_args
        self.assertEqual(kwargs['scalar_names'][0], scalars[0])

    @patch('sina.utils._export_csv')
    def test_export_csv_bad_input_mocked(self, mock):
        """
        Test export with mocked _csv_export() and bad input.

        Test export with of one scalar from sql database to a csv file. Mock
        _export_csv() so we don't actually write to file. Bad input in this
        case is an output_type that is not supported.
        """
        factory = sina_sql.DAOFactory()
        _populate_database_with_data(factory.session)
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
        factory = sina_sql.DAOFactory()
        _populate_database_with_data(factory.session)
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
        factory = sina_sql.DAOFactory()
        _populate_database_with_data(factory.session)
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
            factory=sina_sql.DAOFactory(),
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
        """Test we can write out data to csv."""
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

    # RecordDAO
    def test_recorddao_basic(self):
        """Test that RecordDAO is inserting and getting correctly."""
        record_dao = sina_sql.DAOFactory().createRecordDAO()
        rec = Record(id="spam", type="eggs",
                     data={"eggs": {"value": 12,
                                    "units": None,
                                    "tags": ["runny"]}},
                     files=[{"uri": "eggs.brek",
                             "mimetype": "egg",
                             "tags": ["fried"]}],
                     user_defined={})
        record_dao.insert(rec)
        returned_record = record_dao.get("spam")
        self.assertEquals(returned_record.id, rec.id)
        self.assertEquals(returned_record.type, rec.type)
        returned_scalars = record_dao.get_scalars("spam", ["eggs"])
        self.assertEquals(returned_scalars, rec.data)
        returned_files = record_dao.get_files("spam")
        self.assertEquals(returned_files, rec.files)

        # First test the minimal, JSON-free Record
        pure_obj_record = Record("hello", "there")
        record_dao.insert(pure_obj_record)
        returned_record = record_dao.get("hello")
        self.assertEquals(returned_record.id, pure_obj_record.id)
        self.assertEquals(returned_record.type, pure_obj_record.type)

    def test_recorddao_insert_extras(self):
        """
        Test that RecordDAO is inserting and retrieving files and scalars.

        Doesn't do much testing of functionality, see later tests for that.
        """
        record_dao = sina_sql.DAOFactory().createRecordDAO()
        vals_files = Record(id="spam",
                            type="new_eggs",
                            data={"foo": {"value": 12},
                                  "bar": {"value": "1",
                                          "tags": ["in"]}},
                            files=[{"uri": "ham.png", "mimetype": "png"},
                                   {"uri": "ham.curve", "tags": ["hammy"]}],
                            user_defined={})
        record_dao.insert(vals_files)
        scal = ScalarRange(name="foo", min=12, min_inclusive=True,
                           max=12, max_inclusive=True)
        returned_record = next(record_dao.get_given_scalar(scal))
        self.assertEquals(returned_record.id, vals_files.id)
        no_scal = ScalarRange(name="bar", min=1, min_inclusive=True)
        self.assertFalse(list(record_dao.get_given_scalar(no_scal)))
        file_match = next(record_dao.get_given_document_uri(uri="ham.png"))
        self.assertEquals(file_match.id, vals_files.id)

    @patch(__name__+'.sina_sql.RecordDAO.get')
    def test_recorddao_uri(self, mock_get):
        """Test that RecordDAO is retrieving based on uris correctly."""
        mock_get.return_value = True
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_files(factory.session)
        exact_match = record_dao.get_given_document_uri(uri="beep.png")
        self.assertEqual(len(list(exact_match)), 1)
        end_wildcard = record_dao.get_given_document_uri(uri="beep.%")
        # Note that we're expecting 3 even though there's 4 matches.
        # That's because id "beep" matches twice. So 3 unique.
        # Similar unique-match logic is present in the other asserts
        self.assertEqual(len(list(end_wildcard)), 3)
        mid_wildcard = record_dao.get_given_document_uri(uri="beep%png")
        self.assertEqual(len(list(mid_wildcard)), 2)
        first_wildcard = record_dao.get_given_document_uri(uri="%png")
        self.assertEqual(len(list(first_wildcard)), 3)
        multi_wildcard = record_dao.get_given_document_uri(uri="%.%")
        self.assertEqual(len(list(multi_wildcard)), 4)
        all_wildcard = record_dao.get_given_document_uri(uri="%")
        self.assertEqual(len(list(all_wildcard)), 5)
        ids_only = record_dao.get_given_document_uri(uri="%.%", ids_only=True)
        self.assertIsInstance(ids_only, types.GeneratorType,
                              "Method must return a generator.")
        ids_only = list(ids_only)
        self.assertEqual(len(ids_only), 4)
        self.assertIsInstance(ids_only[0], six.string_types)
        six.assertCountEqual(self, ids_only, ["spam", "spam1", "spam3", "spam4"])

    @patch(__name__+'.sina_sql.RecordDAO.get')
    def test_recorddao_scalar(self, mock_get):
        """Test that RecordDAO is retrieving based on scalars correctly."""
        mock_get.return_value = True
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_data(factory.session)
        too_big_range = ScalarRange(name="spam_scal", max=9,
                                    max_inclusive=True)
        too_big = record_dao.get_given_scalar(too_big_range)
        self.assertFalse(list(too_big))
        too_small_range = ScalarRange(name="spam_scal", min=10.99999,
                                      min_inclusive=False)
        too_small = record_dao.get_given_scalar(too_small_range)
        self.assertFalse(list(too_small))
        just_right_range = ScalarRange(name="spam_scal", min=0,
                                       min_inclusive=True, max=300,
                                       max_inclusive=True)
        just_right = record_dao.get_given_scalar(just_right_range)
        self.assertEqual(len(list(just_right)), 3)
        nonexistant_range = ScalarRange(name="not_here", min=0,
                                        min_inclusive=True, max=300,
                                        max_inclusive=True)
        no_scalar = record_dao.get_given_scalar(nonexistant_range)
        self.assertFalse(list(no_scalar))
        multi_range = ScalarRange(name="spam_scal")
        multi = record_dao.get_given_scalar(multi_range)
        self.assertEqual(len(list(multi)), 3)
        self.assertEqual(mock_get.call_count, 6)
        ids_only = record_dao.get_given_scalar(multi_range, ids_only=True)
        self.assertIsInstance(ids_only, types.GeneratorType,
                              "Method must return generator.")
        ids_only = list(ids_only)
        self.assertEqual(len(ids_only), 3)
        self.assertIsInstance(ids_only[0], six.string_types)
        six.assertCountEqual(self, ids_only, ["spam", "spam2", "spam3"])

    @patch(__name__+'.sina_sql.RecordDAO.get')
    def test_recorddao_many_scalar(self, mock_get):
        """Test that RecordDAO's retrieving on multiple scalars correctly."""
        mock_get.return_value = True
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_data(factory.session)
        spam_and_spam_3 = ScalarRange(name="spam_scal", min=10,
                                      min_inclusive=True)
        spam_3_only = ScalarRange(name="spam_scal_2", max=100)
        one = record_dao.get_given_scalars([spam_and_spam_3,
                                            spam_3_only])
        self.assertEqual(len(list(one)), 1)
        none_fulfill = ScalarRange(name="nonexistant", max=100)
        none = record_dao.get_given_scalars([spam_and_spam_3,
                                             spam_3_only,
                                             none_fulfill])
        self.assertFalse(list(none))
        id_only = record_dao.get_given_scalars([spam_and_spam_3,
                                               spam_3_only],
                                               ids_only=True)
        self.assertIsInstance(id_only, types.GeneratorType,
                              "Method must return a generator.")
        id_only = list(id_only)
        self.assertEqual(len(id_only), 1)
        self.assertEqual(id_only[0], "spam3")

    def test_recorddao_type(self):
        """Test the RecordDAO is retrieving based on type correctly."""
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        rec = Record(id="spam",
                     type="run",
                     user_defined={})
        rec2 = Record(id="spam2",
                      type="run",
                      user_defined={})
        rec3 = Record(id="spam3",
                      type="foo",
                      user_defined={})
        rec4 = Record(id="spam4",
                      type="bar",
                      user_defined={})
        rec5 = Record(id="spam1",
                      type="run",
                      user_defined={})
        record_dao.insert(rec)
        record_dao.insert(rec2)
        record_dao.insert(rec3)
        record_dao.insert(rec4)
        record_dao.insert(rec5)
        get_one = list(record_dao.get_all_of_type("bar"))
        self.assertEqual(len(get_one), 1)
        self.assertIsInstance(get_one[0], Record)
        self.assertEqual(get_one[0].id, rec4.id)
        self.assertEqual(get_one[0].type, rec4.type)
        self.assertEqual(get_one[0].user_defined, rec4.user_defined)
        get_many = list(record_dao.get_all_of_type("run"))
        self.assertEqual(len(get_many), 3)
        get_none = list(record_dao.get_all_of_type("butterscotch"))
        self.assertFalse(get_none)
        ids_only = record_dao.get_all_of_type("run", ids_only=True)
        self.assertIsInstance(ids_only, types.GeneratorType,
                              "Method must return a generator.")
        ids_only = list(ids_only)
        self.assertEqual(len(ids_only), 3)
        self.assertIsInstance(ids_only[0], six.string_types)
        six.assertCountEqual(self, ids_only, ["spam", "spam1", "spam2"])

    def test_recorddao_get_files(self):
        """Test that the RecordDAO is getting files for records correctly."""
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_files(factory.session)
        get_one = record_dao.get_files(id="spam1")
        self.assertEqual(len(get_one), 1)
        self.assertEqual(get_one[0]["uri"], "beep.wav")
        self.assertEqual(get_one[0]["tags"], ["output", "eggs"])
        self.assertFalse(get_one[0]["mimetype"])
        get_more = record_dao.get_files(id="spam")
        self.assertEqual(len(get_more), 2)
        self.assertEqual(get_more[0]["uri"], "beep.pong")

    def test_recorddao_get_data_for_records(self):
        """Test that we're getting data for many records correctly."""
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_data(factory.session)
        all_ids = ["spam", "spam2", "spam3", "eggs"]
        all_scalars = ["spam_scal", "eggs_scal", "spam_scal_2", "val_data"]

        for_one = record_dao.get_data_for_records(id_list=["spam"],
                                                  data_list=all_scalars)
        self.assertEqual(for_one["spam"]["spam_scal"],
                         {"value": 10, "units": "pigs", "tags": ["hammy"]})
        self.assertFalse("eggs_scal" in for_one["spam"].keys())

        for_many = record_dao.get_data_for_records(id_list=all_ids,
                                                   data_list=["spam_scal",
                                                              "spam_scal_2",
                                                              "val_data"])
        six.assertCountEqual(self, for_many.keys(), ["spam", "spam2", "spam3"])
        six.assertCountEqual(self, for_many["spam3"].keys(), ["spam_scal",
                                                              "spam_scal_2",
                                                              "val_data"])
        six.assertCountEqual(self, for_many["spam3"]["val_data"].keys(),
                                                    ["value", "tags"])
        self.assertEqual(for_many["spam3"]["val_data"]["value"], "runny")
        self.assertEqual(for_many["spam3"]["val_data"]["tags"], ["edible"])

        for_none = record_dao.get_data_for_records(id_list=["nope", "nada"],
                                                   data_list=["gone", "away"])
        self.assertFalse(for_none)

    def test_recorddao_get_scalars(self):
        """
        Test that the RecordDAO is getting scalars for a record correctly.

        While covered (mostly) by other tests, it's included for explicity.
        """
        factory = sina_sql.DAOFactory()
        record_dao = factory.createRecordDAO()
        _populate_database_with_data(factory.session)
        get_one = record_dao.get_scalars(id="spam",
                                         scalar_names=["spam_scal"])
        self.assertEqual(len(get_one), 1)
        self.assertEqual(get_one["spam_scal"]["units"], "pigs")
        get_more = record_dao.get_scalars(id="spam",
                                          scalar_names=["spam_scal_2",
                                                        "spam_scal"])
        self.assertEqual(len(get_more), 2)
        self.assertEqual(get_more["spam_scal"]["tags"], ["hammy"])
        self.assertFalse(get_more["spam_scal_2"]["units"])
        self.assertFalse(get_more["spam_scal_2"]["tags"])
        get_gone = record_dao.get_scalars(id="spam",
                                          scalar_names=["value-1"])
        self.assertFalse(get_gone)
        get_norec = record_dao.get_scalars(id="wheeee",
                                           scalar_names=["value-1"])
        self.assertFalse(get_norec)

    # RelationshipDAO
    def test_relationshipdao_basic(self):
        """Test that RelationshipDAO is inserting and getting correctly."""
        relationship_dao = sina_sql.DAOFactory().createRelationshipDAO()
        mock_relationship = MagicMock(subject_id="spam",
                                      object_id="eggs",
                                      predicate="loves")
        relationship_dao.insert(mock_relationship)
        subj = relationship_dao.get(subject_id=mock_relationship.subject_id)
        pred = relationship_dao.get(predicate=mock_relationship.predicate)
        obj_pred = relationship_dao.get(object_id=mock_relationship.object_id,
                                        predicate=mock_relationship.predicate)
        full = relationship_dao.get(subject_id=mock_relationship.subject_id,
                                    object_id=mock_relationship.object_id,
                                    predicate=mock_relationship.predicate)
        for relationship_list in (subj, pred, obj_pred, full):
            result = relationship_list[0]
            self.assertEquals(result.subject_id,
                              mock_relationship.subject_id)
            self.assertEquals(result.object_id,
                              mock_relationship.object_id)
            self.assertEquals(result.predicate,
                              mock_relationship.predicate)
        with self.assertRaises(ValueError) as context:
            relationship_dao.insert(subject_id="spam", object_id="eggs")
        self.assertIn('Must supply either', str(context.exception))

    # RunDAO
    def test_runddao_basic(self):
        """Test that RunDAO is inserting and getting correctly."""
        run_dao = sina_sql.DAOFactory().createRunDAO()
        run = Run(id="spam", version="1.2.3",
                  application="bar", user="bep",
                  user_defined={"boop": "bep"},
                  data={"scalar-strings": {"value":
                                           ["red", "green", "blue"],
                                           "units": None},
                        "scalar-numbers": {"value": [1, 2, 3],
                                           "units": "m"},
                        "foo": {"value": 12,
                                "units": None,
                                "tags": ["in", "on"]},
                        "bar": {"value": "1",
                                "units": None}},)

        run_dao.insert(run)
        returned_run = run_dao.get("spam")
        self.assertEquals(returned_run.id, run.id)
        self.assertEquals(returned_run.raw, run.raw)
        self.assertEquals(returned_run.application, run.application)
        self.assertEquals(returned_run.user, run.user)
        self.assertEquals(returned_run.user_defined, run.user_defined)
        self.assertEquals(returned_run.version, run.version)
        self.assertEquals(returned_run.data, run.data)

    def test_rundao_get_scalars(self):
        """
        Test ability to find Runs by scalars.

        The current version inherits from RecordDAO and does only a little
        extra processing, and most of that in _convert_record_to_run. We're
        really just making sure nothing gets lost between those two.
        """
        # TODO: Test raises question of whether type should be tracked in
        # the scalars table.
        factory = sina_sql.DAOFactory()
        _populate_database_with_data(factory.session)
        run_dao = factory.createRunDAO()
        rec = Record(id="spam2", type="task",
                     user_defined={})
        run = Run(id="spam", user="bep", application="foo",
                  version="1.2", user_defined={"spam": "eggs"})
        run2 = Run(id="spam3", user="egg", application="foo",
                   version="0.4", user_defined={"eggs": "spam"})
        run_dao.record_DAO.insert(rec)
        run_dao.insert_many([run, run2])
        multi_range = ScalarRange(name="spam_scal")
        multi_scalar = list(run_dao.get_given_scalar(multi_range))
        self.assertEqual(len(multi_scalar), 2)
        # They're returned in primary key order
        spam_run = multi_scalar[0]
        self.assertEquals(spam_run.user, run.user)
        self.assertEquals(spam_run.raw, run.raw)

    def test_convert_record_to_run_good(self):
        """Test we return a Run when given a Record with valid input."""
        rec = Record(id="spam", type="run")
        rec["user"] = "bob"
        rec["application"] = "skillet"
        rec["version"] = "1.0"
        factory = sina_sql.DAOFactory()
        run_dao = factory.createRunDAO()
        converted_run = run_dao._convert_record_to_run(record=rec)
        self.assertEqual(converted_run.raw, rec.raw)
        self.assertEqual(type(converted_run), Run)

    def test_convert_record_to_run_bad(self):
        """Test we raise a ValueError when given a Record with bad input."""
        rec = Record(id="spam", type="task ")
        rec["user"] = "bob"
        rec["application"] = "skillet"
        rec["version"] = "1.0"
        factory = sina_sql.DAOFactory()
        run_dao = factory.createRunDAO()
        with self.assertRaises(ValueError) as context:
            run_dao._convert_record_to_run(record=rec)
        self.assertIn('Record must be of subtype Run to convert to Run. Given',
                      str(context.exception))
