import os
import hashlib
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, List

class FileManager:
    """Handles receiving, browsing, and downloading files between Host and Client."""

    def __init__(self, download_dir: Optional[str] = None):
        if not download_dir:
            try:
                user_downloads = Path.home() / "Downloads" / "MeikovaRelay"
            except Exception:
                user_downloads = Path(os.environ.get("LOCALAPPDATA", "C:\temp")) / "MeikovaRelay" / "Downloads"
            user_downloads.mkdir(parents=True, exist_ok=True)
            self.download_dir = str(user_downloads)
        else:
            self.download_dir = download_dir

        self.active_transfers: Dict[str, Dict[str, Any]] = {}

    def start_upload(self, transfer_id: str, filename: str, filesize: int, expected_sha256: str = "", target_dir: Optional[str] = None) -> str:
        filename = unicodedata.normalize('NFC', filename)
        if target_dir:
            target_dir = unicodedata.normalize('NFC', target_dir)
        if target_dir == "desktop" or not target_dir or not os.path.isdir(target_dir):
            try:
                desktop_dir = Path.home() / "Desktop"
                if desktop_dir.is_dir():
                    upload_folder = str(desktop_dir)
                else:
                    upload_folder = self.download_dir
            except Exception:
                upload_folder = self.download_dir
        else:
            upload_folder = target_dir

        norm_parts = [p for p in filename.replace('\\', '/').split('/') if p and p not in ('.', '..')]
        if not norm_parts:
            norm_parts = ["uploaded_file.bin"]
        rel_path = os.path.join(*norm_parts)
        dest_path = os.path.join(upload_folder, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        file_handle = open(dest_path, "wb")
        self.active_transfers[transfer_id] = {
            "path": dest_path,
            "filename": os.path.basename(dest_path),
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

    @staticmethod
    def get_drives() -> List[Dict[str, Any]]:
        import shutil
        drives = []
        if os.name == 'nt':
            for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    try:
                        total, used, free = shutil.disk_usage(drive)
                    except Exception:
                        total, used, free = 0, 0, 0
                    drives.append({
                        "name": drive,
                        "path": drive,
                        "is_dir": True,
                        "total": total,
                        "used": used,
                        "free": free,
                        "percent": int((used / max(1, total)) * 100) if total > 0 else 0
                    })
        else:
            # POSIX root filesystem
            root = "/"
            try:
                total, used, free = shutil.disk_usage(root)
            except Exception:
                total, used, free = 0, 0, 0
            drives.append({
                "name": "Root (/)",
                "path": root,
                "is_dir": True,
                "total": total,
                "used": used,
                "free": free,
                "percent": int((used / max(1, total)) * 100) if total > 0 else 0
            })
            # Check macOS /Volumes or Linux /media, /mnt
            for mount_parent in ["/Volumes", "/media", "/mnt"]:
                if os.path.isdir(mount_parent):
                    try:
                        for entry in os.scandir(mount_parent):
                            if entry.is_dir():
                                try:
                                    t, u, f = shutil.disk_usage(entry.path)
                                except Exception:
                                    t, u, f = 0, 0, 0
                                drives.append({
                                    "name": entry.name,
                                    "path": entry.path,
                                    "is_dir": True,
                                    "total": t,
                                    "used": u,
                                    "free": f,
                                    "percent": int((u / max(1, t)) * 100) if t > 0 else 0
                                })
                    except Exception:
                        pass
        return drives

    def browse_path(self, req_path: str = "") -> Dict[str, Any]:
        """Lists folders and files with stats, breadcrumbs parent, and drive capacities."""
        drives = self.get_drives()
        if not req_path:
            return {"current_path": "", "parent_path": "", "items": drives, "drives": drives}

        req_path = unicodedata.normalize('NFC', req_path)
        target = os.path.abspath(req_path)
        if not os.path.exists(target) or not os.path.isdir(target):
            return {"current_path": req_path, "parent_path": "", "items": [], "drives": drives, "error": "Folder not found"}

        parent_path = os.path.dirname(target)
        if parent_path == target:
            parent_path = ""

        skip_folders = {'System Volume Information', '$RECYCLE.BIN', 'Config.Msi', 'pagefile.sys', 'DumpStack.log.tmp', 'swapfile.sys'}

        items = []
        try:
            for entry in os.scandir(target):
                if entry.name in skip_folders:
                    continue
                try:
                    is_dir = entry.is_dir()
                    stat = entry.stat()
                    ext = "" if is_dir else os.path.splitext(entry.name)[1].lower()
                    items.append({
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": is_dir,
                        "size": 0 if is_dir else stat.st_size,
                        "modified": int(stat.st_mtime * 1000),
                        "ext": ext
                    })
                except Exception:
                    pass
        except Exception as e:
            return {"current_path": target, "parent_path": parent_path, "items": [], "drives": drives, "error": str(e)}

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"current_path": target, "parent_path": parent_path, "items": items[:500], "drives": drives}

    def create_folder(self, parent_dir: str, folder_name: str) -> Dict[str, Any]:
        try:
            parent_dir = unicodedata.normalize('NFC', parent_dir)
            folder_name = unicodedata.normalize('NFC', folder_name)
            safe_name = os.path.basename(folder_name.strip().replace('\\', '/'))
            # Filter Windows forbidden characters
            for invalid_char in '<>:"/\\|?*':
                safe_name = safe_name.replace(invalid_char, '')
            if not safe_name:
                return {"success": False, "error": "Tên thư mục không hợp lệ"}
            new_path = os.path.join(parent_dir, safe_name)
            os.makedirs(new_path, exist_ok=False)
            return {"success": True, "path": new_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_item(self, filepath: str) -> bool:
        import shutil
        try:
            if os.path.isdir(filepath):
                shutil.rmtree(filepath)
                return True
            elif os.path.isfile(filepath):
                os.remove(filepath)
                return True
        except Exception:
            pass
        return False

    def read_file_content(self, filepath: str, max_size: int = 5 * 1024 * 1024) -> Dict[str, Any]:
        """Reads text content of a file directly with automatic encoding detection and binary guard."""
        try:
            filepath = unicodedata.normalize('NFC', filepath)
            target = os.path.abspath(filepath)
            if not os.path.exists(target) or not os.path.isfile(target):
                return {"success": False, "error": "Tệp không tồn tại hoặc là thư mục"}

            stat = os.stat(target)
            if stat.st_size > max_size:
                return {
                    "success": False,
                    "error": f"Tệp quá lớn ({stat.st_size / (1024*1024):.1f} MB > 5MB). Vui lòng dùng tính năng Tải về."
                }

            with open(target, "rb") as f:
                raw = f.read()

            # Binary file check
            if b'\x00' in raw[:8192]:
                return {
                    "success": False,
                    "error": "Tệp nhị phân (Binary) không hỗ trợ chỉnh sửa văn bản trực tiếp."
                }

            # Encodings to try
            encodings = ["utf-8-sig", "utf-8", "cp1258", "cp1252", "latin-1"]
            content = None
            detected_enc = "utf-8"
            for enc in encodings:
                try:
                    content = raw.decode(enc)
                    detected_enc = enc
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if content is None:
                content = raw.decode("utf-8", errors="replace")
                detected_enc = "utf-8 (lossy)"

            return {
                "success": True,
                "filepath": target,
                "filename": os.path.basename(target),
                "content": content,
                "size": stat.st_size,
                "modified": int(stat.st_mtime * 1000),
                "encoding": detected_enc
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_file_content(self, filepath: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Saves text content directly to workstation disk with UTF-8 encoding."""
        try:
            filepath = unicodedata.normalize('NFC', filepath)
            target = os.path.abspath(filepath)
            parent_dir = os.path.dirname(target)
            if not os.path.isdir(parent_dir):
                return {"success": False, "error": "Thư mục đích không tồn tại"}

            enc = "utf-8" if encoding.lower() in ("utf-8", "utf-8-sig") else encoding
            encoded_bytes = content.encode(enc, errors="replace")

            with open(target, "wb") as f:
                f.write(encoded_bytes)

            stat = os.stat(target)
            return {
                "success": True,
                "filepath": target,
                "filename": os.path.basename(target),
                "size": stat.st_size,
                "modified": int(stat.st_mtime * 1000)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def copy_item(self, src: str, dst_dir: str) -> dict:
        """Copies a file or directory into dst_dir."""
        try:
            import shutil
            src = unicodedata.normalize('NFC', src)
            dst_dir = unicodedata.normalize('NFC', dst_dir)
            if not os.path.exists(src):
                return {"success": False, "error": "Nguồn không tồn tại"}
            if not os.path.isdir(dst_dir):
                return {"success": False, "error": "Thư mục đích không tồn tại"}
            base_name = os.path.basename(src.rstrip('\\/'))
            target_path = os.path.join(dst_dir, base_name)
            if os.path.exists(target_path):
                name, ext = os.path.splitext(base_name)
                counter = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(dst_dir, f"{name} - Copy ({counter}){ext}" if ext else f"{name} - Copy ({counter})")
                    counter += 1

            if os.path.isdir(src):
                shutil.copytree(src, target_path)
            else:
                shutil.copy2(src, target_path)
            return {"success": True, "src": src, "dst": target_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def move_item(self, src: str, dst_dir: str) -> dict:
        """Moves / cuts & pastes a file or directory into dst_dir."""
        try:
            import shutil
            src = unicodedata.normalize('NFC', src)
            dst_dir = unicodedata.normalize('NFC', dst_dir)
            if not os.path.exists(src):
                return {"success": False, "error": "Nguồn không tồn tại"}
            if not os.path.isdir(dst_dir):
                return {"success": False, "error": "Thư mục đích không tồn tại"}
            base_name = os.path.basename(src.rstrip('\\/'))
            target_path = os.path.join(dst_dir, base_name)
            if os.path.exists(target_path) and os.path.abspath(target_path).lower() == os.path.abspath(src).lower():
                return {"success": True, "src": src, "dst": target_path}
            shutil.move(src, target_path)
            return {"success": True, "src": src, "dst": target_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def rename_item(self, old_path: str, new_name: str) -> dict:
        """Renames a file or folder in-place."""
        try:
            old_path = unicodedata.normalize('NFC', old_path)
            new_name = unicodedata.normalize('NFC', new_name.strip())
            if not os.path.exists(old_path):
                return {"success": False, "error": "Tệp/thư mục không tồn tại"}
            parent_dir = os.path.dirname(old_path)
            safe_name = os.path.basename(new_name.replace('\\', '/'))
            if not safe_name:
                return {"success": False, "error": "Tên không hợp lệ"}
            new_path = os.path.join(parent_dir, safe_name)
            if os.path.exists(new_path) and os.path.abspath(new_path).lower() != os.path.abspath(old_path).lower():
                return {"success": False, "error": "Tên mới đã tồn tại"}
            os.rename(old_path, new_path)
            return {"success": True, "old_path": old_path, "new_path": new_path, "new_name": safe_name}
        except Exception as e:
            return {"success": False, "error": str(e)}
