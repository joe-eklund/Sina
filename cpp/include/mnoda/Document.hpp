#ifndef MNODA_DOCUMENT_HPP
#define MNODA_DOCUMENT_HPP

/// @file

#include <memory>
#include <vector>

#include "nlohmann/json.hpp"

#include "mnoda/Record.hpp"
#include "mnoda/Relationship.hpp"

namespace mnoda {

/**
 * A Document represents the top-level object of a JSON file conforming to the
 * Mnoda schema. When serialized, these documents can be ingested into a
 * Mnoda database and used with the Sina tool.
 *
 * Documents contain at most two objects: a list of Records and a list of Relationships. A simple, empty document:
 * \code{.json}
 * {
 *     "records": [],
 *     "relationships": []
 * }
 * \endcode
 *
 * The "records" list can contain Record objects and their inheriting types, such as Run (for a full list, please see
 * the inheritance diagram in the Record documentation). The "relationships" list can contain Relationship objects.
 *
 * Documents can be assembled programatically and/or generated from existing JSON. An example of an assembled
 * Document is provided on the main page. To load a Document from an existing JSON file:
 * \code
 * mnoda::Document myDocument = mnoda::loadDocument("path/to/infile.json");
 * \endcode
 *
 * To generate a Document from a JSON string and vice versa:
 * \code
 * nhlohmann::json jObj = "{\"records\":[{\"type\":\"run\",\"id\":\"test\"}],\"relationships\":[]}"_json;
 * mnoda::Document myDocument = mnoda::Document(jObj, mnoda::createRecordLoaderWithAllKnownTypes());
 * std::cout << myDocument.toJson().dump(4) << std::endl;);
 * \endcode
 *
 * You can add further entries to the Document using add():
 * \code
 * std::unique_ptr<mnoda::Record> myRun{new mnoda::Run{someID, "My Sim Code", "1.2.3", "jdoe"}};
 * mnoda::Relationship myRelationship{someID, "comes before", someOtherID};
 * myDocument.add(myRun);
 * myDocument.add(myRelationship);
 * \endcode
 *
 * You can also export your Document to file:
 * \code
 * mnoda::saveDocument(myDocument, "path/to/outfile.json")
 * \endcode
 *
 */
class Document {
public:
    using RecordList = std::vector<std::unique_ptr<Record>>;
    using RelationshipList = std::vector<Relationship>;

    Document() = default;

    // Since we hold pointers to polymorphic objects, we can't support
    // copying or assignment
    Document(Document const &) = delete;

    Document &operator=(Document const &) = delete;

    Document(Document &&) = default;

    Document &operator=(Document &&) = default;

    /**
     * Create a Document from its JSON representation
     *
     * @param asJson the Document as a JSON object
     * @param recordLoader an RecordLoader to use to load the different
     * types of records which may be in the document
     */
    Document(nlohmann::json const &asJson, RecordLoader const &recordLoader);

    /**
     * Add the given record to this document.
     *
     * @param record the record to add
     */
    void add(std::unique_ptr<Record> record);

    /**
     * Get the list of records currently in this document.
     *
     * @return the list of records
     */
    RecordList const &getRecords() const noexcept {
        return records;
    }

    /**
     * Add a relationship to this document
     *
     * @param relationship the relationship to add
     */
    void add(Relationship relationship);

    /**
     * Get the list of relationships in this document.
     *
     * @return the list of relationships
     */
    RelationshipList const &getRelationships() const noexcept {
        return relationships;
    }


    /**
     * Convert this document to its JSON representation.
     *
     * @return the contents of the document as JSON
     */
    nlohmann::json toJson() const;

private:
    RecordList records;
    RelationshipList relationships;
};

/**
 * Save the given Document to the specified location. If the given file exists,
 * it will be overwritten.
 *
 * @param document the Document to save
 * @param fileName the location to which to save the file
 * @throws std::ios::failure if there are any IO errors
 */
void saveDocument(Document const &document, std::string const &fileName);

/**
 * Load a document from the given path. Only records which this library
 * knows about will be able to be loaded.
 *
 * @param path the file system path from which to load the document
 * @return the loaded Document
 */
Document loadDocument(std::string const &path);

/**
 * Load a document from the given path.
 *
 * @param path the file system path from which to load the document
 * @param recordLoader the RecordLoader to use to load the different types
 * of records
 * @return the loaded Document
 */
Document loadDocument(std::string const &path,
        RecordLoader const &recordLoader);

}


#endif //MNODA_DOCUMENT_HPP
