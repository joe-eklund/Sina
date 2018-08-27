"""Contains SQL-specific implementations of our DAOs."""
import os
import numbers
import logging
import sqlalchemy
import json

import sina.dao as dao
import sina.model as model
import sina.datastores.sql_schema as schema

LOGGER = logging.getLogger(__name__)

# String used to identify a sqlite database for SQLALchemy
SQLITE = "sqlite:///"


class RecordDAO(dao.RecordDAO):
    """The DAO specifically responsible for handling Records in SQL."""

    def __init__(self, session):
        """Initialize RecordDAO with session for its SQL database."""
        self.session = session

    def insert(self, record):
        """
        Given a Record, insert it into the current SQL database.

        :param record: A Record to insert
        """
        LOGGER.debug('Inserting {} into SQL.'.format(record))
        self.session.add(schema.Record(record_id=record.record_id,
                                       record_type=record.record_type,
                                       raw=record.raw))
        if record.values:
            self._insert_values(record.record_id, record.values)
        if record.files:
            self._insert_files(record.record_id, record.files)
        self.session.commit()

    def _insert_values(self, record_id, values):
        """
        Insert values into the Scalar and Value tables.

        Does not commit(), caller needs to do that.

        :param record_id: The Record ID to associate the values to.
        :param values: The list of values to insert.
        """
        LOGGER.debug('Inserting {} values to Record ID {}.'
                     .format(len(values), record_id))
        for value in values:
            # Note: SQL doesn't support maps, so we have to convert the
            # tags to a string (if they exist).
            # Using json.dumps() instead of str() (or join()) gives valid JSON
            tags = (json.dumps(value['tags']) if 'tags' in value else None)
            # Check if it's a scalar
            kind = (schema.Scalar if isinstance(value['value'], numbers.Real)
                    else schema.Value)
            self.session.add(kind(record_id=record_id,
                                  name=value['name'],
                                  value=value['value'],
                                  # units might be None, always use get()
                                  units=value.get('units'),
                                  tags=tags))

    def _insert_files(self, record_id, files):
        """
        Insert files into the Document table.

        Does not commit(), caller needs to do that.

        :param record_id: The Record ID to associate the files to.
        :param files: The list of files to insert.
        """
        LOGGER.debug('Inserting {} files to record id={}.'
                     .format(len(files), record_id))
        for entry in files:
            tags = (json.dumps(entry['tags']) if 'tags' in entry else None)
            self.session.add(schema.Document(record_id=record_id,
                                             uri=entry['uri'],
                                             mimetype=entry.get('mimetype'),
                                             tags=tags))

    def get(self, record_id):
        """
        Given a record_id, return match (if any) from SQL database.

        :param record_id: The id of the record to return

        :returns: A record matching that id or None
        """
        LOGGER.debug('Getting record with id={}'.format(record_id))
        query = (self.session.query(schema.Record)
                 .filter(schema.Record.record_id == record_id).one())
        return model.Record(record_id=query.record_id,
                            record_type=query.record_type,
                            raw=query.raw)

    def get_all_of_type(self, record_type):
        """
        Given a type of record, return all Records of that type.

        :param record_type: The type of record to return, ex: run

        :returns: a list of Records of that type
        """
        LOGGER.debug('Getting all records of type {}.'.format(record_type))
        query = (self.session.query(schema.Record)
                 .filter(schema.Record.record_type == record_type))
        return [model.Record(record_id=x.record_id,
                             record_type=x.record_type,
                             raw=x.raw) for x in query.all()]

    def get_given_document_uri(self, uri, accepted_ids_list=None):
        """
        Return all records associated with documents whose uris match some arg.

        Supports the use of % as a wildcard character.

        :param uri: The uri to use as a search term, such as "foo.png"
        :param accepted_ids_list: A list of ids to restrict the search to.
                                  If not provided, all ids will be used.

        :returns: A list of matching records (or None)
        """
        LOGGER.debug('Getting all records related to uri={}.'.format(uri))
        if accepted_ids_list:
            LOGGER.debug('Restricting to {} ids.'.format(len(accepted_ids_list)))
        # Note: Mixed results on whether SQLAlchemy's optimizer is smart enough
        # to have %-less LIKE operate on par with ==, hence this:
        if '%' in uri:
            query = (self.session.query(schema.Document.record_id)
                     .filter(schema.Document.uri.like(uri)).distinct())
        else:
            query = (self.session.query(schema.Document.record_id)
                     .filter(schema.Document.uri == uri).distinct())
        if accepted_ids_list is not None:
            query = query.filter(schema.Document
                                 .record_id.in_(accepted_ids_list))
        return self.get_many(x[0] for x in query.all())

    # TODO: While not part of the original implementation, we now have
    # the ability to store non-scalar values as well, so we'll need a query
    # to search on them, as well as a more user-facing query that can be
    # given a list of values and call both this and the aforementioned method.
    def get_given_scalars(self, scalar_range_list):
        """
        Return all records with scalars fulfilling some criteria.

        Note that this is a logical 'and'--the record must satisfy every
        conditional provided (which is also why this can't simply call
        get_given_scalar() as get_many() does with get()).

        :param scalar_range_list: A list of 'sina.ScalarRange's describing the
                                 different criteria.

        :returns: A list of Records fitting the criteria
        """
        LOGGER.debug('Getting all records with scalars within the following '
                     'ranges: {}'.format(scalar_range_list))
        query = self.session.query(schema.Scalar.record_id)
        query = self._apply_scalar_ranges_to_query(query, scalar_range_list)
        out = query.all()
        if out:
            return self.get_many(x[0] for x in query.all())
        else:
            return []

    def get_given_scalar(self, scalar_range):
        """
        Return all records with scalars fulfilling some criteria.

        :param scalar_range: A sina.ScalarRange describing the criteria.

        :returns: A list of Records fitting the criteria
        """
        return self.get_given_scalars([scalar_range])

    def _apply_scalar_ranges_to_query(self, query, scalars):
        """
        Filter query object based on list of ScalarRanges.

        Uses parameter substitution to get around limitations of SQLAlchemy OR
        construct.

        :param query: A SQLAlchemy query object
        :param scalars: A list of ScalarRanges to apply to the query object

        :returns: <query>, now filtering on <scalars>
        """
        LOGGER.debug('Filtering <query={}> with <scalars={}>.'.format(query, scalars))
        search_args = {}
        for index, scalar in enumerate(scalars):
            search_args["scalar_name{}".format(index)] = scalar.name
            search_args["min{}".format(index)] = scalar.min
            search_args["max{}".format(index)] = scalar.max

        query = query.filter(sqlalchemy
                             .or_(self._build_range_filter(scalar, index)
                                  for index, scalar in enumerate(scalars)))
        query = (query.group_by(schema.Scalar.record_id)
                      .having(sqlalchemy.text("{} = {}"
                              .format(sqlalchemy.func
                                      .count(schema.Scalar.record_id),
                                      len(scalars)))))
        query = query.params(search_args)
        return query

    def _build_range_filter(self, scalar, index=0):
        """
        Build a TextClause to filter a SQL query using range parameters.

        Helper method to _apply_scalar_ranges_to_query. Needed in order to use
        parameter substitution and circumvent some filter limitations.

        Example clause as raw SQL:

        WHERE Scalar.name=:scalar_name0 AND Scalar.value<right_num0

        :param scalar: The scalar used to build the query.
        :param index: optional offset of this criteria if using multiple
                      criteria. Used for building var names for
                      parameterization.

        :returns: a TextClause object for use in a SQLAlchemy statement
        """
        LOGGER.debug('Building TextClause filter from <scalar={}> and index={}.'
                     .format(scalar, index))
        conditions = ["(Scalar.name IS :scalar_name{} AND Scalar.value"
                      .format(index)]

        scalar.validate_and_standardize_range()

        # Check if both sides of the range are the same number (not None)
        # Used for a small simplification: '=[5,5]' == '=5'
        if (scalar.min is not None) and (scalar.min == scalar.max):
            conditions.append(" = :min{}".format(index))

        # If both sides are None, we're only testing that a number exists
        elif scalar.min is None and scalar.max is None:
            conditions.append(" IS NOT NULL")

        else:
            if scalar.min is not None:
                conditions.append(" >= " if scalar.min_inclusive else " > ")
                conditions.append(":min{}".format(index))
            if (scalar.min is not None) and (scalar.max is not None):
                # If two-sided range, begin preparing new condition
                conditions.append(" AND Scalar.value ")
            if scalar.max is not None:
                conditions.append(" <= " if scalar.max_inclusive else " < ")
                conditions.append(":max{}".format(index))

        conditions.append(")")
        return sqlalchemy.text(''.join(conditions))

    def get_scalars(self, record_id, scalar_names):
        """
        Retrieve scalars for a given record id.

        Scalars are returned in alphabetical order.

        :param record_id: The record id to find scalars for
        :param scalar_names: A list of the names of scalars to return
        :return: A list of scalar JSON objects matching the Mnoda specification
        """
        # Note lack of filtering on tags. Something to consider.
        # Also, how to handle values? Separate method? Search both tables?
        LOGGER.debug('Getting scalars={} for record id={}'
                     .format(scalar_names, record_id))
        scalars = []
        query = (self.session.query(schema.Scalar.name, schema.Scalar.value,
                                    schema.Scalar.units, schema.Scalar.tags)
                 .filter(schema.Scalar.record_id == record_id)
                 .filter(schema.Scalar.name.in_(scalar_names))
                 .order_by(schema.Scalar.name.asc()).all())
        for entry in query:
            # SQL doesn't handle maps. so tags are stored as JSON lists.
            # This converts them to Python.
            tags = json.loads(entry[3]) if entry[3] else None
            scalars.append({'name': entry[0],
                            'value': entry[1],
                            'units': entry[2],
                            'tags': tags})
        return scalars

    def get_files(self, record_id):
        """
        Retrieve files for a given record id.

        Files are returned in the alphabetical order of their URIs

        :param record_id: The record id to find files for
        :return: A list of file JSON objects matching the Mnoda specification
        """
        LOGGER.debug('Getting files for record id={}'.format(record_id))
        query = (self.session.query(schema.Document.uri, schema.Document.mimetype,
                                    schema.Document.tags)
                             .filter(schema.Document.record_id == record_id)
                             .order_by(schema.Document.uri.asc()).all())
        files = []
        for entry in query:
            tags = json.loads(entry[2]) if entry[2] else None
            files.append({'uri': entry[0], 'mimetype': entry[1], 'tags': tags})
        return files


class RelationshipDAO(dao.RelationshipDAO):
    """The DAO responsible for handling Relationships in SQL."""

    def __init__(self, session):
        """Initialize RelationshipDAO with session for its SQL database."""
        self.session = session

    def insert(self, relationship=None, subject_id=None,
               object_id=None, predicate=None):
        """
        Given some Relationship, import it into the SQL database.

        This can create an entry from either an existing relationship object
        or from its components (subject id, object id, predicate). If all four
        are provided, the Relationship will be used.

        A Relationship describes the connection between two objects in the
        form <subject_id> <predicate> <object_id>, ex:

        Task44 contains Run2001

        :param subject_id: The record_id of the subject.
        :param object_id: The record_id of the object.
        :param predicate: A string describing the relationship.
        :param relationship: A Relationship object to build entry from.
        """
        LOGGER.debug('Inserting relationship={}, subject_id={}, object_id={}, '
                     'and predicate={}.'.format(relationship,
                                                subject_id,
                                                object_id,
                                                predicate))
        if relationship and subject_id and object_id and predicate:
            LOGGER.warning('Given relationship object and '
                           'subject_id/object_id/predicate objects. Using '
                           'relationship.')
        if not (relationship or (subject_id and object_id and predicate)):
            msg = ("Must supply either Relationship or subject_id, "
                   "object_id, and predicate.")
            LOGGER.error(msg)
            raise ValueError(msg)
        if relationship:
            subject_id = relationship.subject_id
            object_id = relationship.object_id
            predicate = relationship.predicate
        self.session.add(schema.Relationship(subject_id=subject_id,
                                             object_id=object_id,
                                             predicate=predicate))
        self.session.commit()

    # Note that get() is implemented by its parent.

    # TODO: Ongoing question of whether these should return generators.

    def _get_given_subject_id(self, subject_id, predicate=None):
        """
        Given record id, return all Relationships with that id as subject.

        Returns None if none found. Wrapped by get(). Optionally filters on
        predicate as well.

        :param subject_id: The subject_id of Relationships to return
        :param predicate: Optionally, the Relationship predicate to filter on.

        :returns: A list of Relationships fitting the criteria or None.
        """
        LOGGER.debug('Getting relationships related to subject_id={} and '
                     'predicate={}.'.format(subject_id, predicate))
        query = (self.session.query(schema.Relationship)
                 .filter(schema.Relationship.subject_id == subject_id))
        if predicate:
            query.filter(schema.Relationship.predicate == predicate)

        return self._build_relationships(query.all())

    def _get_given_object_id(self, object_id, predicate=None):
        """
        Given record id, return all Relationships with that id as object.

        Returns None if none found. Wrapped by get(). Optionally filters on
        predicate as well.

        :param object_id: The object_id of Relationships to return
        :param predicate: Optionally, the Relationship predicate to filter on.

        :returns: A list of Relationships fitting the criteria or None.
        """
        LOGGER.debug('Getting relationships related to object_id={} and '
                     'predicate={}.'.format(object_id, predicate))
        query = (self.session.query(schema.Relationship)
                 .filter(schema.Relationship.object_id == object_id))
        if predicate:
            query.filter(schema.Relationship.predicate == predicate)

        return self._build_relationships(query.all())

    def _get_given_predicate(self, predicate):
        """
        Given predicate, return all Relationships with that predicate.

        :param predicate: The predicate describing Relationships to return

        :returns: A list of Relationships fitting the criteria
        """
        LOGGER.debug('Getting relationships related to predicate={}.'
                     .format(predicate))
        query = (self.session.query(schema.Relationship)
                 .filter(schema.Relationship.predicate == predicate))

        return self._build_relationships(query.all())

    def _build_relationships(self, query):
        """
        Given query results, build a list of Relationships.

        :param query: The query results to build from.
        """
        LOGGER.debug('Building relationships from query={}'.format(query))
        relationships = []
        for relationship in query:
            rel_obj = model.Relationship(subject_id=relationship.subject_id,
                                         object_id=relationship.object_id,
                                         predicate=relationship.predicate)
            relationships.append(rel_obj)
        return relationships


class RunDAO(dao.RunDAO):
    """DAO responsible for handling Runs, (Record subtype), in SQL."""

    def __init__(self, session, recordDAO):
        """Initialize RunDAO and assign a contained RecordDAO."""
        super(RunDAO, self).__init__(recordDAO)
        self.session = session
        self.record_DAO = recordDAO

    def insert(self, run):
        """
        Given a Run, import it into the current SQL database.

        :param run: A Run to import
        """
        LOGGER.debug('Inserting {} into SQL.'.format(run))
        # Note: SQL doesn't support maps, so we have to convert the
        # user_defined to a string (if it exists).
        user_defined = (str(run.user_defined) if run.user_defined else None)
        self.session.add(schema.Run(record_id=run.record_id,
                                    application=run.application,
                                    user=run.user,
                                    user_defined=user_defined,
                                    version=run.version))
        self.record_DAO.insert(run)
        self.session.commit()
        # TODO: Previous question carried forward:
        # When inserting to Run, should we also insert to Record?
        # Or should the "all Runs are Records" be expressed elsewhere?

    def get(self, run_id):
        """
        Given a run's id, return match (if any) from SQL database.

        :param run_id: The id of some run

        :returns: A run matching that identifier or None
        """
        LOGGER.debug('Getting run with id: {}'.format(run_id))
        record_portion = (self.session.query(schema.Record)
                          .filter(schema.Record.record_id == run_id).one())
        run_portion = (self.session.query(schema.Run)
                       .filter(schema.Run.record_id == run_id).one())
        return model.Run(record_id=run_id,
                         raw=record_portion.raw,
                         application=run_portion.application,
                         user=run_portion.user,
                         user_defined=run_portion.user_defined,
                         version=run_portion.version)

    def _convert_record_to_run(self, record):
        """
        Build a Run using a Record and run metadata.

        A variant of get() for internal use which allows us to recycle some of
        Record's functionality. Given a Record, pulls in its information from
        Run and folds it into a new Run object. Allows us to skip an extra read
        of the record table.

        :param record: A Record object to build the Run from.

        :returns: A Run representing the Record plus metadata.
        """
        LOGGER.debug('Converting {} to run.'.format(record))
        run_portion = (self.session.query(schema.Run)
                       .filter(schema.Run.record_id == record.record_id).one())
        return model.Run(record_id=record.record_id,
                         raw=record.raw,
                         application=run_portion.application,
                         user=run_portion.user,
                         user_defined=run_portion.user_defined,
                         version=run_portion.version)


class DAOFactory(dao.DAOFactory):
    """
    Build SQL-backed DAOs for interacting with Mnoda-based objects.

    Includes Records, Relationships, etc.
    """

    def __init__(self, db_path=None):
        """
        Initialize a Factory with a path to its backend.

        Currently supports only SQLite.

        :param db_path: Path to the database to use as a backend. If None, will
                        use an in-memory database.
        """
        self.db_path = db_path
        if db_path:
            engine = sqlalchemy.create_engine(SQLITE + db_path)
            if not os.path.exists(db_path):
                schema.Base.metadata.create_all(engine)
        else:
            engine = sqlalchemy.create_engine('sqlite:///')
            schema.Base.metadata.create_all(engine)
        session = sqlalchemy.orm.sessionmaker(bind=engine)
        self.session = session()

    def createRecordDAO(self):
        """
        Create a DAO for interacting with records.

        :returns: a RecordDAO
        """
        return RecordDAO(session=self.session)

    def createRelationshipDAO(self):
        """
        Create a DAO for interacting with relationships.

        :returns: a RelationshipDAO
        """
        return RelationshipDAO(session=self.session)

    def createRunDAO(self):
        """
        Create a DAO for interacting with runs.

        :returns: a RunDAO
        """
        return RunDAO(session=self.session,
                      recordDAO=self.createRecordDAO())

    def __repr__(self):
        """Return a string representation of a SQL DAOFactory."""
        return 'SQL DAOFactory <db_path={}>'.format(self.db_path)