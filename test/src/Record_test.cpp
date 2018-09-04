#include <stdexcept>
#include <typeinfo>

#include "gtest/gtest.h"
#include "gmock/gmock.h"

#include "mnoda/Record.hpp"
#include "mnoda/CppBridge.hpp"

#include "mnoda/testing/TestRecord.hpp"

namespace mnoda { namespace testing { namespace {

using ::testing::ElementsAre;
using ::testing::HasSubstr;
using ::testing::DoubleEq;

char const EXPECTED_TYPE_KEY[] = "type";
char const EXPECTED_LOCAL_ID_KEY[] = "local_id";
char const EXPECTED_GLOBAL_ID_KEY[] = "id";
char const EXPECTED_DATA_KEY[] = "data";
char const EXPECTED_FILES_KEY[] = "files";
char const EXPECTED_USER_DEFINED_KEY[] = "user_defined";

TEST(Record, create_typeMissing) {
    nlohmann::json originalJson{
            {EXPECTED_LOCAL_ID_KEY, "the ID"}
    };
    try {
        Record record{originalJson};
        FAIL() << "Should have failed due to missing type";
    } catch (std::invalid_argument const &expected) {
        EXPECT_THAT(expected.what(), HasSubstr(EXPECTED_TYPE_KEY));
    }
}

TEST(Record, create_localId_fromJson) {
    nlohmann::json originalJson {
            {EXPECTED_TYPE_KEY, "my type"},
            {EXPECTED_LOCAL_ID_KEY, "the ID"}
    };
    Record record{originalJson};
    EXPECT_EQ("my type", record.getType());
    EXPECT_EQ("the ID", record.getId().getId());
    EXPECT_EQ(IDType::Local, record.getId().getType());
}

TEST(Record, create_globalId_fromJson) {
    nlohmann::json originalJson {
            {EXPECTED_TYPE_KEY, "my type"},
            {EXPECTED_GLOBAL_ID_KEY, "the ID"}
    };
    Record record{originalJson};
    EXPECT_EQ("my type", record.getType());
    EXPECT_EQ("the ID", record.getId().getId());
    EXPECT_EQ(IDType::Global, record.getId().getType());
}

TEST(Record, create_globalId_data) {
    nlohmann::json originalJson {
        {EXPECTED_TYPE_KEY, "my type"},
        {EXPECTED_GLOBAL_ID_KEY, "the ID"}
    };
    originalJson[EXPECTED_DATA_KEY].emplace_back(
        R"({"name": "datum name 1",
            "value": "value 1"})"_json
    );
    originalJson[EXPECTED_DATA_KEY].emplace_back(
        R"({"name": "datum name 2",
            "value": 2.22,
            "units": "g/L",
            "tags": ["tag1","tag2"]})"_json
    );
    Record record{originalJson};
    auto &data = record.getData();
    ASSERT_EQ(2u, data.size());
    EXPECT_EQ("datum name 1", data[0].getName());
    EXPECT_EQ("value 1", data[0].getValue());

    EXPECT_EQ("datum name 2", data[1].getName());
    EXPECT_THAT(2.22, DoubleEq(data[1].getScalar()));
    EXPECT_EQ("g/L", data[1].getUnits());
    EXPECT_EQ("tag1", data[1].getTags()[0]);
    EXPECT_EQ("tag2", data[1].getTags()[1]);
}

TEST(Record, create_globalId_files) {
    nlohmann::json originalJson{
            {EXPECTED_TYPE_KEY, "my type"},
            {EXPECTED_GLOBAL_ID_KEY, "the ID"}
    };
    originalJson[EXPECTED_FILES_KEY].emplace_back(R"({"uri": "uri1"})"_json);
    originalJson[EXPECTED_FILES_KEY].emplace_back(R"({"uri": "uri2"})"_json);
    originalJson[EXPECTED_FILES_KEY].emplace_back(R"({"uri": "uri3"})"_json);

    Record record{originalJson};
    auto &files = record.getFiles();
    ASSERT_EQ(3u, files.size());
    EXPECT_EQ("uri1", files[0].getUri());
    EXPECT_EQ("uri2", files[1].getUri());
    EXPECT_EQ("uri3", files[2].getUri());
}

TEST(Record, create_fromJson_userDefined) {
    nlohmann::json asJson{
            {EXPECTED_TYPE_KEY, "my type"},
            {EXPECTED_GLOBAL_ID_KEY, "the ID"},
            {EXPECTED_USER_DEFINED_KEY, R"({
                    "k1": "v1",
                    "k2": 123,
                    "k3": [1, 2, 3]
                     })"_json}
    };

    Record record{asJson};
    auto const &userDefined = record.getUserDefinedContent();
    EXPECT_EQ("v1", userDefined["k1"]);
    EXPECT_EQ(123, userDefined["k2"]);
    EXPECT_THAT(userDefined["k3"], ElementsAre(1, 2, 3));
}

TEST(Record, getUserDefined_initialConst) {
    ID id{"the id", IDType::Local};
    Record const record{id, "my type"};
    nlohmann::json const &userDefined = record.getUserDefinedContent();
    EXPECT_EQ(nlohmann::json::value_t::null, userDefined.type());
}

TEST(Record, getUserDefined_initialNonConst) {
    ID id{"the id", IDType::Local};
    Record record{id, "my type"};
    nlohmann::json &initialUserDefined = record.getUserDefinedContent();
    EXPECT_EQ(nlohmann::json::value_t::null, initialUserDefined.type());
    initialUserDefined["foo"] = 123;
    EXPECT_EQ(123, record.getUserDefinedContent()["foo"]);
}

TEST(Record, toJson_localId) {
    ID id{"the id", IDType::Global};
    Record record{id, "my type"};
    auto asJson = record.toJson();
    EXPECT_TRUE(asJson.is_object());
    EXPECT_EQ("my type", asJson[EXPECTED_TYPE_KEY]);
    EXPECT_EQ("the id", asJson[EXPECTED_GLOBAL_ID_KEY]);
    EXPECT_EQ(0, asJson.count(EXPECTED_LOCAL_ID_KEY));
}

TEST(Record, toJson_globalId) {
    ID id{"the id", IDType::Local};
    Record record{id, "my type"};
    auto asJson = record.toJson();
    EXPECT_TRUE(asJson.is_object());
    EXPECT_EQ("my type", asJson[EXPECTED_TYPE_KEY]);
    EXPECT_EQ("the id", asJson[EXPECTED_LOCAL_ID_KEY]);
    EXPECT_EQ(0, asJson.count(EXPECTED_GLOBAL_ID_KEY));
}

TEST(Record, toJson_userDefined) {
    ID id{"the id", IDType::Local};
    Record record{id, "my type"};
    record.setUserDefinedContent(R"({
        "k1": "v1",
        "k2": 123,
        "k3": [1, 2, 3]
    })"_json);

    auto asJson = record.toJson();

    auto userDefined = asJson[EXPECTED_USER_DEFINED_KEY];
    EXPECT_EQ("v1", userDefined["k1"]);
    EXPECT_EQ(123, userDefined["k2"]);
    EXPECT_THAT(userDefined["k3"], ElementsAre(1, 2, 3));
}

TEST(Record, toJson_data) {
    ID id{"the id", IDType::Local};
    Record record{id, "my type"};
    Datum datum1 = Datum{"name1","value1"};
    datum1.setUnits("some units");
    datum1.setTags({"tag1"});
    record.add(datum1);
    record.add(Datum{"name2",2});
    auto asJson = record.toJson();
    std::cout << asJson;
    ASSERT_EQ(2u, asJson[EXPECTED_DATA_KEY].size());
    EXPECT_EQ("name1", asJson[EXPECTED_DATA_KEY][0]["name"]);
    EXPECT_EQ("value1", asJson[EXPECTED_DATA_KEY][0]["value"]);
    EXPECT_EQ("some units", asJson[EXPECTED_DATA_KEY][0]["units"]);
    EXPECT_EQ("tag1", asJson[EXPECTED_DATA_KEY][0]["tags"][0]);

    EXPECT_EQ("name2", asJson[EXPECTED_DATA_KEY][1]["name"]);
    EXPECT_THAT(asJson[EXPECTED_DATA_KEY][1]["value"].get<double>(), DoubleEq(2.));
    EXPECT_TRUE(asJson[EXPECTED_DATA_KEY][1]["units"].is_null());
    EXPECT_TRUE(asJson[EXPECTED_DATA_KEY][1]["tags"].is_null());
}

TEST(Record, toJson_files) {
    ID id{"the id", IDType::Local};
    Record record{id, "my type"};
    File file{"uri1"};
    file.setMimeType("mt1");
    record.add(file);
    record.add(File{"uri2"});
    auto asJson = record.toJson();
    ASSERT_EQ(2u, asJson[EXPECTED_FILES_KEY].size());
    EXPECT_EQ("uri1", asJson[EXPECTED_FILES_KEY][0]["uri"]);
    EXPECT_EQ("mt1", asJson[EXPECTED_FILES_KEY][0]["mimetype"]);
    EXPECT_EQ("uri2", asJson[EXPECTED_FILES_KEY][1]["uri"]);
    EXPECT_TRUE(asJson[EXPECTED_FILES_KEY][1]["mimetype"].is_null());
}

TEST(RecordLoader, load_missingLoader) {
    RecordLoader loader;
    nlohmann::json asJson{
            {EXPECTED_GLOBAL_ID_KEY, "the ID"},
            {EXPECTED_TYPE_KEY, "unknownType"}
    };
    auto loaded = loader.load(asJson);
    auto &actualType = typeid(*loaded);
    EXPECT_EQ(typeid(Record), actualType) << "Type was " << actualType.name();
}

TEST(RecordLoader, load_loaderPresent) {
    RecordLoader loader;
    EXPECT_FALSE(loader.canLoad("TestInt"));
    EXPECT_FALSE(loader.canLoad("TestString"));

    loader.addTypeLoader("TestInt",
            [](nlohmann::json const &value) {
                return internal::make_unique<TestRecord<int>>(value);
            });
    EXPECT_TRUE(loader.canLoad("TestInt"));

    loader.addTypeLoader("TestString",
            [](nlohmann::json const &value) {
                return internal::make_unique<TestRecord<std::string>>(value);
            });
    EXPECT_TRUE(loader.canLoad("TestString"));

    nlohmann::json asJson{
            {EXPECTED_GLOBAL_ID_KEY, "the ID"},
            {EXPECTED_TYPE_KEY, "TestString"},
            {TEST_RECORD_VALUE_KEY, "The value"},
    };
    auto loaded = loader.load(asJson);
    auto testObjPointer = dynamic_cast<TestRecord<std::string> *>(loaded.get());
    ASSERT_NE(nullptr, testObjPointer);
    ASSERT_EQ("The value", testObjPointer->getValue());
}

TEST(RecordLoader, createRecordLoaderWithAllKnownTypes) {
    RecordLoader loader = createRecordLoaderWithAllKnownTypes();
    EXPECT_TRUE(loader.canLoad("run"));
}

}}}
