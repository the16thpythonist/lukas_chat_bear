"""
Tests for ConfigurationRepository.

Tests configuration storage, retrieval, and type conversion logic.
Type conversion is critical business logic that must work correctly.
"""

import json

from sqlalchemy.orm import Session

from src.models import Configuration
from src.repositories.config_repo import ConfigurationRepository


class TestConfigurationRetrieval:
    """Test configuration retrieval operations."""

    def test_get_config(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving a configuration record by key.

        Protects against: Query failures, incorrect filtering.
        """
        config = config_repo.get_config("random_dm_interval_hours")

        assert config is not None
        assert config.key == "random_dm_interval_hours"
        assert config.value == "24"

    def test_get_config_not_found(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test get_config returns None when key doesn't exist.

        Protects against: Exceptions on missing keys, incorrect default behavior.
        """
        config = config_repo.get_config("nonexistent_key")

        assert config is None

    def test_get_all_configs(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving all configurations as a dictionary.

        Should return typed values (not string representations).

        Protects against: Missing configurations, incorrect data retrieval.
        """
        # Use get_all_configs_dict() to get dictionary of key-value pairs
        all_configs = config_repo.get_all_configs_dict()

        # Seeded database has 3 configs
        assert len(all_configs) >= 3
        assert "random_dm_interval_hours" in all_configs
        assert "proactive_engagement_probability" in all_configs
        assert "enable_image_generation" in all_configs


class TestTypeConversion:
    """Test configuration value type conversion logic."""

    def test_get_value_integer(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving integer configuration value.

        String "24" should be converted to integer 24.

        Protects against: Type conversion failures, incorrect data types.
        """
        value = config_repo.get_value("random_dm_interval_hours")

        assert isinstance(value, int)
        assert value == 24

    def test_get_value_float(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving float configuration value.

        String "0.15" should be converted to float 0.15.

        Protects against: Precision loss, type conversion errors.
        """
        value = config_repo.get_value("proactive_engagement_probability")

        assert isinstance(value, float)
        assert value == 0.15

    def test_get_value_boolean_true(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving boolean true value.

        String "true" should be converted to bool True.

        Protects against: Boolean parsing errors, case sensitivity issues.
        """
        value = config_repo.get_value("enable_image_generation")

        assert isinstance(value, bool)
        assert value is True

    def test_get_value_boolean_variants(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that boolean conversion handles various representations.

        "true", "1", "yes" should all convert to True.

        Protects against: Inconsistent boolean representation, parsing failures.
        """
        # Test various true representations
        for true_value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            config = Configuration(
                key=f"test_bool_{true_value}",
                value=true_value,
                value_type="boolean",
                description=f"Test boolean value {true_value}",
            )
            test_session.add(config)
            test_session.commit()

            result = config_repo.get_value(f"test_bool_{true_value}")
            assert result is True, f"'{true_value}' should convert to True"

    def test_get_value_boolean_false(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that boolean conversion handles false values.

        Anything other than "true", "1", "yes" should be False.

        Protects against: Incorrect boolean interpretation.
        """
        for false_value in ["false", "False", "0", "no", "No"]:
            config = Configuration(
                key=f"test_bool_{false_value}",
                value=false_value,
                value_type="boolean",
                description=f"Test boolean value {false_value}",
            )
            test_session.add(config)
            test_session.commit()

            result = config_repo.get_value(f"test_bool_{false_value}")
            assert result is False, f"'{false_value}' should convert to False"

    def test_get_value_json_dict(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving JSON object configuration.

        JSON string should be parsed to Python dict.

        Protects against: JSON parsing failures, data structure corruption.
        """
        json_data = {"key1": "value1", "key2": 123}
        config = Configuration(
            key="test_json_dict",
            value=json.dumps(json_data),
            value_type="json",
            description="Test JSON dict configuration",
        )
        test_session.add(config)
        test_session.commit()

        value = config_repo.get_value("test_json_dict")

        assert isinstance(value, dict)
        assert value == json_data

    def test_get_value_json_list(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving JSON array configuration.

        JSON array string should be parsed to Python list.

        Protects against: JSON array parsing failures.
        """
        json_data = ["item1", "item2", 123]
        config = Configuration(
            key="test_json_list",
            value=json.dumps(json_data),
            value_type="json",
            description="Test JSON list configuration",
        )
        test_session.add(config)
        test_session.commit()

        value = config_repo.get_value("test_json_list")

        assert isinstance(value, list)
        assert value == json_data

    def test_get_value_string(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test retrieving string configuration value.

        String values should be returned as-is.

        Protects against: Unnecessary string processing, encoding issues.
        """
        config = Configuration(
            key="test_string",
            value="Hello, World!",
            value_type="string",
            description="Test string configuration",
        )
        test_session.add(config)
        test_session.commit()

        value = config_repo.get_value("test_string")

        assert isinstance(value, str)
        assert value == "Hello, World!"

    def test_get_value_with_default(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test get_value returns default when key doesn't exist.

        Protects against: Errors on missing configuration, null pointer issues.
        """
        value = config_repo.get_value("nonexistent_key", default=42)

        assert value == 42

    def test_get_value_invalid_integer_returns_default(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that invalid integer value returns default instead of crashing.

        When stored value cannot be converted to integer, should return default.

        Protects against: Application crashes on malformed data.
        """
        config = Configuration(
            key="bad_integer",
            value="not_a_number",
            value_type="integer",
            description="Test invalid integer configuration",
        )
        test_session.add(config)
        test_session.commit()

        value = config_repo.get_value("bad_integer", default=100)

        assert value == 100

    def test_get_value_invalid_json_returns_default(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that invalid JSON returns default instead of crashing.

        Protects against: JSON parsing exceptions breaking application.
        """
        config = Configuration(
            key="bad_json",
            value="{invalid json}",
            value_type="json",
            description="Test invalid JSON configuration",
        )
        test_session.add(config)
        test_session.commit()

        value = config_repo.get_value("bad_json", default={"default": "value"})

        assert value == {"default": "value"}


class TestConfigurationCreation:
    """Test configuration creation and update operations."""

    def test_set_value_creates_new_integer(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new integer configuration.

        Should auto-detect type and store correctly.

        Protects against: Type detection failures, creation errors.
        """
        config = config_repo.set_value("new_int", 42, "Test integer config")

        assert config.key == "new_int"
        assert config.value == "42"
        assert config.value_type == "integer"
        assert config.description == "Test integer config"

    def test_set_value_creates_new_float(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new float configuration.

        Protects against: Float type detection failures.
        """
        config = config_repo.set_value("new_float", 3.14, "Test float config")

        assert config.value == "3.14"
        assert config.value_type == "float"

    def test_set_value_creates_new_boolean(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new boolean configuration.

        Protects against: Boolean type detection failures.
        """
        config = config_repo.set_value("new_bool", True, "Test boolean config")

        assert config.value == "True"
        assert config.value_type == "boolean"

    def test_set_value_creates_new_dict(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new JSON dict configuration.

        Should serialize dict to JSON string.

        Protects against: Dict serialization failures, JSON encoding errors.
        """
        test_dict = {"key": "value", "number": 123}
        config = config_repo.set_value("new_dict", test_dict, "Test dict config")

        assert config.value_type == "json"
        assert json.loads(config.value) == test_dict

    def test_set_value_creates_new_list(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new JSON list configuration.

        Protects against: List serialization failures.
        """
        test_list = ["item1", "item2", 123]
        config = config_repo.set_value("new_list", test_list, "Test list config")

        assert config.value_type == "json"
        assert json.loads(config.value) == test_list

    def test_set_value_creates_new_string(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test creating a new string configuration.

        Protects against: String type detection failures.
        """
        config = config_repo.set_value("new_string", "hello", "Test string config")

        assert config.value == "hello"
        assert config.value_type == "string"

    def test_set_value_updates_existing(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test updating an existing configuration value.

        Should update value and type, not create duplicate.

        Protects against: Duplicate keys, update failures.
        """
        count_before = seeded_db.query(Configuration).count()

        # Update existing config
        config = config_repo.set_value("random_dm_interval_hours", 48, "Updated description")

        count_after = seeded_db.query(Configuration).count()

        # Should not create new record
        assert count_before == count_after
        assert config.value == "48"
        assert config.description == "Updated description"

    def test_set_value_updates_type_when_changed(self, seeded_db: Session, config_repo: ConfigurationRepository):
        """
        Test that updating a value also updates its type if changed.

        Changing from "24" (int) to "24.5" (float) should update value_type.

        Protects against: Type mismatch, stale metadata.
        """
        # Original is integer
        original = config_repo.get_config("random_dm_interval_hours")
        assert original.value_type == "integer"

        # Update to float
        config_repo.set_value("random_dm_interval_hours", 24.5)

        # Verify type updated
        updated = config_repo.get_config("random_dm_interval_hours")
        assert updated.value_type == "float"
        assert updated.value == "24.5"

    def test_set_value_with_updated_by_user(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test setting configuration with updated_by_user_id tracking.

        Audit trail: should track which user made the configuration change.

        Protects against: Missing audit trail, compliance issues.
        """
        from src.models import TeamMember

        user = TeamMember(slack_user_id="U_ADMIN", display_name="Admin")
        test_session.add(user)
        test_session.flush()

        config = config_repo.set_value(
            "tracked_config",
            "value",
            "Tracked config",
            updated_by_user_id=user.id,
        )

        assert config.updated_by_user_id == user.id

    def test_set_value_auto_generates_description(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that set_value generates a description if none provided.

        Protects against: Empty descriptions, missing metadata.
        """
        config = config_repo.set_value("auto_desc_key", "value")

        assert config.description == "Configuration for auto_desc_key"


class TestDefaultConfigSeeding:
    """Test default configuration seeding."""

    def test_seed_default_configs(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test seeding default configurations.

        Should create all default configs with correct values and types.

        Protects against: Missing default configs, initialization failures.
        """
        config_repo.seed_default_configs()

        # Verify expected defaults exist
        expected_keys = [
            "random_dm_interval_hours",
            "thread_response_probability",
            "reaction_probability",
            "image_post_interval_days",
            "conversation_retention_days",
            "max_context_messages",
            "max_tokens_per_request",
        ]

        for key in expected_keys:
            config = config_repo.get_config(key)
            assert config is not None, f"Missing default config: {key}"
            assert config.description is not None

    def test_seed_default_configs_idempotent(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that seeding default configs is idempotent.

        Running seed twice should not create duplicates or overwrite custom values.

        Protects against: Duplicate configs, data loss on re-initialization.
        """
        # Seed defaults
        config_repo.seed_default_configs()

        # Update one config
        config_repo.set_value("random_dm_interval_hours", 48)

        # Seed again
        config_repo.seed_default_configs()

        # Verify custom value not overwritten
        value = config_repo.get_value("random_dm_interval_hours")
        assert value == 48, "Custom value should not be overwritten by seeding"

        # Verify no duplicates
        count = test_session.query(Configuration).filter_by(
            key="random_dm_interval_hours"
        ).count()
        assert count == 1

    def test_seed_default_configs_correct_types(self, test_session: Session, config_repo: ConfigurationRepository):
        """
        Test that seeded default configs have correct types.

        Integer and float values should be properly typed.

        Protects against: Type detection failures, incorrect default data.
        """
        config_repo.seed_default_configs()

        # Test integer type
        dm_interval = config_repo.get_value("random_dm_interval_hours")
        assert isinstance(dm_interval, int)

        # Test float type
        probability = config_repo.get_value("thread_response_probability")
        assert isinstance(probability, float)
