import unittest
import os
import shutil
import json
import tempfile
from core.config_manager import ConfigManager

class TestConfigManagerProfiles(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests
        self.test_dir = tempfile.mkdtemp()
        self.profiles_dir = os.path.join(self.test_dir, "profiles")
        self.config_file = os.path.join(self.test_dir, "webhtc_config.json")

        # Patch ConfigManager to use temporary paths
        # We need to monkeypatch the module-level constants or the instance variables
        # Since they are used in many places, we'll try to override them in the instance
        # if possible, or monkeypatch the module.

        import core.config_manager
        self.orig_profiles_dir = core.config_manager.PROFILES_DIR
        self.orig_config_file = core.config_manager.CONFIG_FILE

        core.config_manager.PROFILES_DIR = self.profiles_dir
        core.config_manager.CONFIG_FILE = self.config_file

        self.cm = ConfigManager()

    def tearDown(self):
        # Restore original constants
        import core.config_manager
        core.config_manager.PROFILES_DIR = self.orig_profiles_dir
        core.config_manager.CONFIG_FILE = self.orig_config_file

        # Remove temporary directory
        shutil.rmtree(self.test_dir)

        # Ensure no test files left in project root if any were created by mistake
        if os.path.exists("test_outside.json"):
            os.remove("test_outside.json")

    def test_save_profile_normal(self):
        self.assertTrue(self.cm.save_profile("valid_profile"))
        self.assertTrue(os.path.exists(os.path.join(self.profiles_dir, "valid_profile.json")))

    def test_save_profile_traversal(self):
        # Attempting to save outside PROFILES_DIR
        self.assertFalse(self.cm.save_profile("../test_outside"))
        # Check that it's not in the temporary dir's parent
        self.assertFalse(os.path.exists(os.path.join(self.test_dir, "test_outside.json")))
        # Check that it's not in the project root
        self.assertFalse(os.path.exists("test_outside.json"))

    def test_load_profile_normal(self):
        self.cm.save_profile("valid_profile")
        # Reset CM to clear memory profiles
        self.cm = ConfigManager()
        self.assertTrue(self.cm.load_profile("valid_profile"))
        self.assertEqual(self.cm.get_active_profile(), "valid_profile")

    def test_load_profile_traversal(self):
        # Create a file outside the profiles dir but inside our test temp dir
        outside_file = os.path.join(self.test_dir, "test_outside.json")
        with open(outside_file, "w") as f:
            json.dump({"test": "data"}, f)

        self.assertFalse(self.cm.load_profile("../test_outside"))
        # Should NOT load the data from outside
        self.assertNotEqual(self.cm.get("test"), "data")

    def test_delete_profile_normal(self):
        self.cm.save_profile("to_delete")
        self.assertTrue(self.cm.delete_profile("to_delete"))
        self.assertFalse(os.path.exists(os.path.join(self.profiles_dir, "to_delete.json")))

    def test_delete_profile_traversal(self):
        outside_file = os.path.join(self.test_dir, "test_outside.json")
        with open(outside_file, "w") as f:
            f.write("{}")

        self.assertFalse(self.cm.delete_profile("../test_outside"))
        self.assertTrue(os.path.exists(outside_file))

    def test_invalid_names(self):
        invalid_names = [
            "",
            None,
            "/absolute/path",
            "../../../etc/passwd",
            "profile\0name",
            "subdir/profile"
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(self.cm.save_profile(name))
                self.assertFalse(self.cm.load_profile(name))
                self.assertFalse(self.cm.delete_profile(name))

if __name__ == "__main__":
    unittest.main()
