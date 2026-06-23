"""Unit tests for aws-s3-glacier-restore."""
import importlib.machinery
import importlib.util
import os
import sys
import threading
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

# Import the module despite its hyphenated name and missing .py extension
_module_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aws-s3-glacier-restore")
_loader = importlib.machinery.SourceFileLoader("glacier_restore", _module_path)
_spec = importlib.util.spec_from_loader("glacier_restore", _loader)
mod = importlib.util.module_from_spec(_spec)
sys.modules["glacier_restore"] = mod
_spec.loader.exec_module(mod)

# Aliases for convenience
AtomicInteger = mod.AtomicInteger
get_matching_s3_keys_and_sizes = mod.get_matching_s3_keys_and_sizes
_list_prefix = mod._list_prefix
restore = mod.restore
check_status = mod.check_status


def _make_client_error(code, message="error"):
    return ClientError(
        {"Error": {"Code": code, "Message": message}}, "operation_name"
    )


# ---------------------------------------------------------------------------
# AtomicInteger
# ---------------------------------------------------------------------------
class TestAtomicInteger:
    def test_initial_value(self):
        ai = AtomicInteger()
        assert ai.value() == 0

    def test_initial_value_custom(self):
        ai = AtomicInteger(42)
        assert ai.value() == 42

    def test_inc_default(self):
        ai = AtomicInteger()
        ai.inc()
        assert ai.value() == 1

    def test_inc_custom(self):
        ai = AtomicInteger(10)
        ai.inc(5)
        assert ai.value() == 15

    def test_thread_safety(self):
        ai = AtomicInteger()
        threads = [threading.Thread(target=ai.inc) for _ in range(1000)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert ai.value() == 1000


# ---------------------------------------------------------------------------
# get_matching_s3_keys_and_sizes
# ---------------------------------------------------------------------------
class TestGetMatchingS3KeysAndSizes:
    def test_rejects_non_s3_scheme(self):
        with pytest.raises(Exception, match="Prefix scheme must be s3"):
            list(get_matching_s3_keys_and_sizes("http://bucket/prefix"))

    @patch("glacier_restore.boto3")
    def test_single_page(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "data/file1.txt", "Size": 100},
                {"Key": "data/file2.txt", "Size": 200},
            ]
        }
        results = list(get_matching_s3_keys_and_sizes("s3://mybucket/data/"))
        assert results == [
            ("s3://mybucket/data/file1.txt", 100),
            ("s3://mybucket/data/file2.txt", 200),
        ]

    @patch("glacier_restore.boto3")
    def test_pagination(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.list_objects_v2.side_effect = [
            {
                "Contents": [{"Key": "data/a.txt", "Size": 10}],
                "NextContinuationToken": "token123",
            },
            {
                "Contents": [{"Key": "data/b.txt", "Size": 20}],
            },
        ]
        results = list(get_matching_s3_keys_and_sizes("s3://mybucket/data/"))
        assert len(results) == 2
        assert results[1] == ("s3://mybucket/data/b.txt", 20)
        assert mock_client.list_objects_v2.call_count == 2

    @patch("glacier_restore.boto3")
    def test_no_contents_raises(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.list_objects_v2.return_value = {}
        with pytest.raises(Exception, match="No S3 files for prefix"):
            list(get_matching_s3_keys_and_sizes("s3://mybucket/empty/"))

    @patch("glacier_restore.boto3")
    def test_list_prefix_returns_list(self, mock_boto3):
        """_list_prefix materialises the generator so a pool can map over it."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.list_objects_v2.return_value = {
            "Contents": [{"Key": "data/file1.txt", "Size": 100}]
        }
        result = _list_prefix("s3://mybucket/data/")
        assert result == [("s3://mybucket/data/file1.txt", 100)]


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------
class TestRestore:
    def _make_to_restore(self, **overrides):
        base = {
            "file": {"key": "/data/file.txt", "bucket": "mybucket", "size": 100},
            "days": 5,
            "tier": "Standard",
        }
        base.update(overrides)
        return base

    @patch("glacier_restore.boto3")
    def test_successful_restore(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        restore(self._make_to_restore())
        mock_client.restore_object.assert_called_once()
        call_kwargs = mock_client.restore_object.call_args
        assert call_kwargs[1]["Bucket"] == "mybucket"
        assert call_kwargs[1]["Key"] == "data/file.txt"
        assert call_kwargs[1]["RestoreRequest"]["Days"] == 5

    @patch("glacier_restore.boto3")
    def test_restore_to_destination_bucket(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mod.destination_bucket = "dest-bucket"
        try:
            restore(self._make_to_restore())
            call_kwargs = mock_client.restore_object.call_args[1]
            assert "OutputLocation" in call_kwargs["RestoreRequest"]
            assert call_kwargs["RestoreRequest"]["OutputLocation"]["S3"]["BucketName"] == "dest-bucket"
        finally:
            mod.destination_bucket = None

    @patch("glacier_restore.boto3")
    def test_restore_already_in_progress(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = _make_client_error(
            "RestoreAlreadyInProgress"
        )
        # Should not raise
        restore(self._make_to_restore())

    @patch("glacier_restore.boto3")
    def test_invalid_object_state(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = _make_client_error(
            "InvalidObjectState"
        )
        restore(self._make_to_restore())

    @patch("glacier_restore.boto3")
    def test_no_such_key(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = _make_client_error("NoSuchKey")
        restore(self._make_to_restore())

    @patch("glacier_restore.boto3")
    def test_unknown_error_is_raised(self, mock_boto3):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = _make_client_error("SomeOtherError")
        with pytest.raises(ClientError):
            restore(self._make_to_restore())

    @patch("glacier_restore.time")
    @patch("glacier_restore.boto3")
    def test_operation_aborted_retries(self, mock_boto3, mock_time):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        # Fail twice with OperationAborted, then succeed
        mock_client.restore_object.side_effect = [
            _make_client_error("OperationAborted"),
            _make_client_error("OperationAborted"),
            None,
        ]
        restore(self._make_to_restore(), max_tries=5)
        assert mock_client.restore_object.call_count == 3
        assert mock_time.sleep.call_count == 2

    @patch("glacier_restore.time")
    @patch("glacier_restore.boto3")
    def test_max_retries_exceeded(self, mock_boto3, mock_time):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = _make_client_error("OperationAborted")
        restore(self._make_to_restore(), max_tries=3)
        assert mock_client.restore_object.call_count == 3

    @patch("glacier_restore.time")
    @patch("glacier_restore.boto3")
    def test_expedited_not_available_retries(self, mock_boto3, mock_time):
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.restore_object.side_effect = [
            _make_client_error("GlacierExpeditedRetrievalNotAvailable"),
            None,
        ]
        restore(self._make_to_restore(), max_tries=5)
        assert mock_client.restore_object.call_count == 2
        mock_time.sleep.assert_called_once_with(60)

    def test_days_none_without_destination_bucket(self):
        mod.destination_bucket = None
        with pytest.raises(ValueError, match="days_to_keep is required"):
            restore(self._make_to_restore(days=None))


# ---------------------------------------------------------------------------
# check_status
# ---------------------------------------------------------------------------
class TestCheckStatus:
    def _make_to_check(self):
        return {"file": {"key": "/data/file.txt", "bucket": "mybucket", "size": 100}}

    @patch("glacier_restore.boto3")
    def test_standard_storage_class(self, mock_boto3):
        """HeadObject omits StorageClass for STANDARD — should not crash."""
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {}  # no StorageClass key
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.not_on_glacier_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_glacier_not_being_restored(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {"StorageClass": "GLACIER"}
        result = check_status(self._make_to_check())
        assert result is not None
        assert result["bucket"] == "mybucket"

    @patch("glacier_restore.boto3")
    def test_glacier_restore_in_progress(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mod.in_progress_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "GLACIER",
            "Restore": 'ongoing-request="true"',
        }
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.restored_count.value() == 0
        assert mod.in_progress_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_glacier_restore_completed(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "GLACIER",
            "Restore": 'ongoing-request="false", expiry-date="Mon, 01 Jan 2030 00:00:00 GMT"',
        }
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.restored_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_deep_archive_recognized(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {"StorageClass": "DEEP_ARCHIVE"}
        result = check_status(self._make_to_check())
        # Not being restored, should return the file dict
        assert result is not None

    @patch("glacier_restore.boto3")
    def test_intelligent_tiering_accessible(self, mock_boto3):
        """IT object with no ArchiveStatus is instantly readable, not Glacier."""
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {"StorageClass": "INTELLIGENT_TIERING"}
        result = check_status(self._make_to_check())
        # Accessible -> no restore needed, no file returned
        assert result is None
        assert mod.not_on_glacier_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_intelligent_tiering_archive_access(self, mock_boto3):
        """IT in Archive Access tier genuinely needs a restore."""
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "INTELLIGENT_TIERING",
            "ArchiveStatus": "ARCHIVE_ACCESS",
        }
        result = check_status(self._make_to_check())
        assert result is not None
        assert mod.not_on_glacier_count.value() == 0

    @patch("glacier_restore.boto3")
    def test_intelligent_tiering_deep_archive_access(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "INTELLIGENT_TIERING",
            "ArchiveStatus": "DEEP_ARCHIVE_ACCESS",
        }
        result = check_status(self._make_to_check())
        assert result is not None
        assert mod.not_on_glacier_count.value() == 0

    @patch("glacier_restore.boto3")
    def test_intelligent_tiering_restore_in_progress(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mod.in_progress_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "INTELLIGENT_TIERING",
            "ArchiveStatus": "ARCHIVE_ACCESS",
            "Restore": 'ongoing-request="true"',
        }
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.in_progress_count.value() == 1
        assert mod.restored_count.value() == 0

    @patch("glacier_restore.boto3")
    def test_intelligent_tiering_restore_completed(self, mock_boto3):
        mod.restored_count = AtomicInteger()
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {
            "StorageClass": "INTELLIGENT_TIERING",
            "ArchiveStatus": "ARCHIVE_ACCESS",
            "Restore": 'ongoing-request="false", expiry-date="Mon, 01 Jan 2030 00:00:00 GMT"',
        }
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.restored_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_glacier_ir_no_restore_needed(self, mock_boto3):
        """Glacier Instant Retrieval is readable directly, no restore job."""
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {"StorageClass": "GLACIER_IR"}
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.not_on_glacier_count.value() == 1

    @patch("glacier_restore.boto3")
    def test_reduced_redundancy_not_glacier(self, mock_boto3):
        mod.not_on_glacier_count = AtomicInteger()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {"StorageClass": "REDUCED_REDUNDANCY"}
        result = check_status(self._make_to_check())
        assert result is None
        assert mod.not_on_glacier_count.value() == 1
