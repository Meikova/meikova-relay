import unittest
import sys
import tarfile
import zipfile
import tempfile
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.build import (
    create_deb_package,
    create_linux_tarball,
    create_macos_tarball,
    create_windows_zip,
    generate_checksums,
    build
)

class TestBuildAndPackaging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dist_dir = Path(self.temp_dir.name)
        # Create a mock binary file
        self.mock_bin = self.dist_dir / "mock_bin"
        self.mock_bin.write_bytes(b"ELF_MOCK_STANDALONE_BINARY_CONTENT")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_deb_package(self):
        deb_path = self.dist_dir / "meikova-relay-host_1.0.0_amd64.deb"
        result = create_deb_package(self.mock_bin, deb_path, version="1.0.0")
        self.assertTrue(result.exists())
        self.assertGreater(result.stat().st_size, 100)

        # Verify ar archive header
        with open(result, "rb") as f:
            magic = f.read(8)
            self.assertEqual(magic, b"!<arch>\n")
            h1 = f.read(60)
            self.assertTrue(h1.startswith(b"debian-binary"))
            data1 = f.read(4)
            self.assertEqual(data1, b"2.0\n")

    def test_create_linux_tarball(self):
        tar_path = self.dist_dir / "meikova-relay-host-linux-x64.tar.gz"
        result = create_linux_tarball(self.mock_bin, tar_path)
        self.assertTrue(result.exists())

        with tarfile.open(result, "r:gz") as tar:
            names = tar.getnames()
            self.assertIn("meikova-relay-host", names)
            self.assertIn("install.sh", names)

    def test_create_macos_tarball(self):
        tar_path = self.dist_dir / "meikova-relay-host-macos.tar.gz"
        result = create_macos_tarball(self.mock_bin, tar_path)
        self.assertTrue(result.exists())

        with tarfile.open(result, "r:gz") as tar:
            names = tar.getnames()
            self.assertIn("meikova-relay-host", names)
            self.assertIn("install.sh", names)

    def test_create_windows_zip(self):
        zip_path = self.dist_dir / "MeikovaRelayHost-windows-x64.zip"
        exe_mock = self.dist_dir / "MeikovaRelayHost.exe"
        exe_mock.write_bytes(b"MZ_PE_MOCK_EXECUTABLE")
        result = create_windows_zip(exe_mock, zip_path)
        self.assertTrue(result.exists())

        with zipfile.ZipFile(result, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("MeikovaRelayHost.exe", namelist)
            self.assertIn("README.txt", namelist)

    def test_generate_checksums(self):
        f1 = self.dist_dir / "test_file.bin"
        content = b"TEST_PAYLOAD_FOR_HASHING"
        f1.write_bytes(content)
        expected_sha = hashlib.sha256(content).hexdigest()

        chk_file = generate_checksums(self.dist_dir)
        self.assertTrue(chk_file.exists())
        text = chk_file.read_text(encoding="utf-8")
        self.assertIn(expected_sha, text)
        self.assertIn("test_file.bin", text)

    def test_build_all_targets_skip_pyinstaller(self):
        build(target="all", dist_dir=self.dist_dir, skip_pyinstaller=True)
        # Verify Windows artifacts
        self.assertTrue((self.dist_dir / "MeikovaRelayHost-windows-x64.zip").exists())
        # Verify Linux artifacts
        self.assertTrue((self.dist_dir / "meikova-relay-host_amd64.deb").exists())
        self.assertTrue((self.dist_dir / "meikova-relay-host-linux-x64.tar.gz").exists())
        # Verify macOS artifacts
        self.assertTrue((self.dist_dir / "meikova-relay-host-macos.tar.gz").exists())
        # Verify checksums
        self.assertTrue((self.dist_dir / "SHA256SUMS.txt").exists())

    def test_windows_manifest_configuration(self):
        manifest_path = REPO_ROOT / "host_agent" / "MeikovaRelayHost.manifest"
        self.assertTrue(manifest_path.exists())
        content = manifest_path.read_text(encoding="utf-8")
        self.assertIn('uiAccess="true"', content)
        self.assertIn("PerMonitorV2", content)

if __name__ == "__main__":
    unittest.main()
