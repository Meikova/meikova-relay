import os
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

class FileManager:
    """Handles receiving and sending files between Host and Client."""

    def __init__(self, download_dir: Optional[str] = None):
        if not download_dir:
            # Default to user's Downloads/TitanRemote
            user_downloads = Path.home() / "Downloads" / "TitanRemote"
            user_downloads.mkdir(parents=True, exist_ok=True)
            self.download_dir = str(user_downloads)
        else:
            self.download_dir = download_dir

        self.active_transfers: Dict[str, Dict[str, Any]] = {}

    def start_upload(self, transfer_id: str, filename: str, filesize: int, expected_sha256: str = "") -> str:
        safe_name = os.path.basename(filename)
        dest_path = os.path.join(self.download_dir, safe_name)

        # Open file in write-binary mode
        file_handle = open(dest_path, "wb")
        self.active_transfers[transfer_id] = {
            "path": dest_path,
            "filename": safe_name,
            "expected_size": filesize,
            "received_size": 0,
            "hasher": hashlib.sha256(),
            "expected_sha256": expected_sha256,
            "handle": file_handle
        }
        return dest_path

    def write_chunk(self, transfer_id: str, chunk_data: bytes) -> Dict[str, Any]:
        if transfer_id not in self.active_transfers:
            return {"status": "error", "message": "Unknown transfer ID"}

        item = self.active_transfers[transfer_id]
        item["handle"].write(chunk_data)
        item["hasher"].update(chunk_data)
        item["received_size"] += len(chunk_data)

        progress = int((item["received_size"] / max(1, item["expected_size"])) * 100)
        return {
            "status": "progress",
            "progress": min(100, progress),
            "received": item["received_size"]
        }

    def finish_upload(self, transfer_id: str) -> Dict[str, Any]:
        if transfer_id not in self.active_transfers:
            return {"status": "error", "message": "Unknown transfer ID"}

        item = self.active_transfers.pop(transfer_id)
        item["handle"].close()

        calculated_sha = item["hasher"].hexdigest()
        is_valid = True
        if item["expected_sha256"]:
            is_valid = (calculated_sha.lower() == item["expected_sha256"].lower())

        return {
            "status": "success" if is_valid else "corrupted",
            "filename": item["filename"],
            "path": item["path"],
            "sha256": calculated_sha,
            "valid": is_valid
        }

    def list_files(self) -> list:
        results = []
        try:
            for entry in os.scandir(self.download_dir):
                if entry.is_file():
                    stat = entry.stat()
                    results.append({
                        "name": entry.name,
                        "size": stat.st_size,
                        "modified": int(stat.st_mtime * 1000)
                    })
        except Exception:
            pass
        return sorted(results, key=lambda x: x["modified"], reverse=True)
