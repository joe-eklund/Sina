"""Integration tests for the CLI and API working together."""
import unittest
import os

import cassandra.cqlengine.connection as connection
import cassandra.cqlengine.management as management
from nose.plugins.attrib import attr

from sina import launcher

TEMP_DB_NAME = "temp_sqlite_testfile.sqlite"
# CQLEngine needs a keyspace to start. Will not be edited.
INITIAL_KEYSPACE_NAME = "system_traces"
# Name of keyspace to create and then delete.
TEMP_KEYSPACE_NAME = "temp_keyspace_testing_sina"


class TestSQLIntegration(unittest.TestCase):
    """SQL tests for how the suite fits together that mimic a user's steps."""

    def setUp(self):
        """Prepare for each test by initializing parser and preparing args."""
        self.parser = launcher.setup_arg_parser()
        # We need to provide initial minimal args, but will change per test
        self.args = self.parser.parse_args(['ingest', '-d', 'null.sqlite',
                                            'null.json'])
        self.location = os.path.dirname(os.path.realpath(__file__))
        self.created_db = os.path.join(self.location, TEMP_DB_NAME)

    def tearDown(self):
        """Clean up after each test by removing the created_db tempfile."""
        try:
            os.remove(self.created_db)
        except OSError:
            pass

    # Create a sql database and query it
    def test_sql_workflow(self):
        """Verify integration between CLI and API for SQL."""
        self.args.source = ",".join([os.path.join(self.location,
                                                  "test_files/mnoda_1.json"),
                                     os.path.join(self.location,
                                                  "test_files/mnoda_2.json")])
        self.args.subparser_name = 'ingest'
        self.args.database = self.created_db
        launcher.ingest(self.args)
        self.args.subparser_name = 'query'
        self.args.scalar = 'scalar-1=387.6'
        self.args.uri = 'foo.png'
        self.args.raw = ''
        self.args.id = False
        matches = launcher.query(self.args)
        self.assertEqual(matches[0].record_id, "child_1")
        self.args.scalar = 'scalar-4=0'
        matches = launcher.query(self.args)
        self.assertEqual(matches, [])
        # Export test goes here


@attr('cassandra')
class TestCassIntegration(unittest.TestCase):
    """Cass tests for how the suite fits together that mimic a user's steps."""

    def setUp(self):
        """Prepare for each test by initializing parser and preparing args."""
        self.parser = launcher.setup_arg_parser()
        # We need to provide initial minimal args, but will change per test
        self.args = self.parser.parse_args(['ingest', '-d', '127.0.0.1',
                                            'null.json'])
        self.location = os.path.dirname(os.path.realpath(__file__))

    def tearDown(self):
        """Clean up after each test by removing the created_db tempfile."""
        try:
            management.drop_keyspace(TEMP_KEYSPACE_NAME)
        except OSError:
            pass

    # Create a cass database and query it
    def test_cass_workflow(self):
        """Verify integration between CLI and API for Cassandra."""
        # We have to create a keyspace first
        connection.setup(['127.0.0.1'], INITIAL_KEYSPACE_NAME)
        management.create_keyspace_simple(TEMP_KEYSPACE_NAME, 1)
        self.args.source = ",".join([os.path.join(self.location,
                                                  "test_files/mnoda_1.json"),
                                     os.path.join(self.location,
                                                  "test_files/mnoda_2.json")])
        self.args.subparser_name = 'ingest'
        self.args.database = '127.0.0.1'
        self.args.database_type = 'cass'
        self.args.cass_keyspace = TEMP_KEYSPACE_NAME
        launcher.ingest(self.args)
        self.args.subparser_name = 'query'
        self.args.scalar = 'scalar-1=387.6'
        self.args.uri = 'foo.png'
        self.args.raw = ''
        self.args.id = False
        matches = launcher.query(self.args)
        self.assertEqual(matches[0].record_id, "child_1")
        self.args.scalar = 'scalar-4=0'
        matches = launcher.query(self.args)
        self.assertEqual(matches, [])
        # Export test goes here
