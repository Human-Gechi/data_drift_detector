import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Union
import pandas as pd
from log import get_ingest_logger

data_logger = get_ingest_logger()

class DataFileLoader:

    DEFAULT_SEARCH_DIRS = [
        "~/Downloads",
        "~/Documents",
        "~/Desktop",
        "~/OneDrive/Desktop"
        "."
    ]

    SUPPORTED_EXTENSIONS = {
        ".csv": pd.read_csv,
        ".jsonl": lambda f: pd.read_json(f, lines=True),
        ".json": pd.read_json,
        ".xlsx": pd.read_excel,
        ".xls": pd.read_excel,
        ".parquet": pd.read_parquet,
    }

    BANNED_DIRS = {
        "venv", ".venv", "env", ".git", "__pycache__",
        "node_modules", "$recycle.bin", "system volume information",
        "appdata", "windows", "program files", "program files (x86)",
        "windowsapps", "microsoft shared", "common files",
    }

    def __init__(self, search_dirs: Optional[Union[str, List[str]]] = None) -> None:
        if search_dirs is None:
            dirs = self.DEFAULT_SEARCH_DIRS
        elif isinstance(search_dirs, str):
            dirs = [search_dirs]
        else:
            dirs = search_dirs

        self.search_dirs = self._expand_dirs(dirs)
        self._file_cache: Dict[str, Path] = {}
        self._walk_cache: Dict[str, List[Path]] = {}

    def _expand_dirs(self, dirs: List[str]) -> List[str]:
        expanded = []
        for d in dirs:
            try:
                p = Path(d).expanduser().resolve()
                if p.is_dir():
                    expanded.append(str(p))
                else:
                    data_logger.warning(f"Skipping non‑existent directory: {d} → {p}")
            except Exception as e:
                data_logger.warning(f"Invalid directory '{d}': {e}")
        return expanded

    def is_virtualenv_folder(self, folder_path: Union[str, Path]) -> bool:
        return (Path(folder_path) / "pyvenv.cfg").is_file()

    def _should_skip_dir(self, dir_name: str) -> bool:
        if dir_name.startswith("."):
            return True
        return dir_name.lower() in self.BANNED_DIRS

    def _walk_directory(self, root_path: Path) -> Iterator[Path]:
        root_str = str(root_path)
        if root_str in self._walk_cache:
            yield from self._walk_cache[root_str]
            return

        discovered = []
        try:
            with os.scandir(root_path) as it:
                for entry in it:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir():
                        if self._should_skip_dir(entry.name):
                            continue
                        if self.is_virtualenv_folder(entry.path):
                            continue
                        yield from self._walk_directory(Path(entry.path))
                    else:
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in self.SUPPORTED_EXTENSIONS:
                            file_path = Path(entry.path)
                            discovered.append(file_path)
                            yield file_path
        except (OSError, PermissionError) as e:
            data_logger.debug(f"Cannot scan {root_path}: {e}")

        self._walk_cache[root_str] = discovered

    def find(self, filename: str) -> Optional[Path]:
        if filename in self._file_cache:
            return self._file_cache[filename]

        for search_dir in self.search_dirs:
            for file_path in self._walk_directory(Path(search_dir)):
                if file_path.name == filename:
                    self._file_cache[filename] = file_path
                    return file_path
        return None

    def find_all(self, extensions: Optional[List[str]] = None) -> List[Path]:
        if extensions is None:
            extensions = list(self.SUPPORTED_EXTENSIONS.keys())
        extensions = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions]
        extensions = [ext.lower() for ext in extensions]

        all_files = []
        for search_dir in self.search_dirs:
            for file_path in self._walk_directory(Path(search_dir)):
                if file_path.suffix.lower() in extensions:
                    all_files.append(file_path)
        return all_files

    def load(self, filename: str) -> Optional[pd.DataFrame]:
        file_path = self.find(filename)
        if not file_path:
            data_logger.error(f"File not found: {filename}")
            return None

        ext = file_path.suffix.lower()
        loader = self.SUPPORTED_EXTENSIONS.get(ext)
        if not loader:
            data_logger.warning(f"Unsupported file type: {ext}")
            return None

        try:
            df = loader(file_path)
            for col in df.select_dtypes(include=["object", "string"]).columns:
                if any(k in col.lower() for k in ["date", "time", "timestamp", "created", "updated"]):
                    df[col] = pd.to_datetime(df[col], errors="coerce")
            df = df.convert_dtypes()
            data_logger.info(f"Loaded {file_path} ({df.shape[0]} rows, {df.shape[1]} cols)")
            return df
        except Exception as e:
            data_logger.error(f"Error loading {file_path}: {e}")
            return None

    def get_file_hashes(self, file_path: Optional[Union[str, Path]] = None) -> Dict[str, Dict[str, str]]:
        hashes = {}
        if file_path is not None:
            path_obj = Path(file_path)
            if not path_obj.is_absolute():
                found = self.find(str(file_path))
                if not found:
                    data_logger.error(f"File not found: {file_path}")
                    return {}
                files_to_process = [found]
            else:
                files_to_process = [path_obj]
        else:
            files_to_process = self.find_all()

        for fpath in files_to_process:
            try:
                sha256 = hashlib.sha256()
                with open(fpath, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha256.update(chunk)
                hashes[str(fpath)] = {
                    "hash": sha256.hexdigest(),
                    "checked_at": datetime.now().isoformat(),
                }
            except Exception as e:
                data_logger.warning(f"Could not hash {fpath}: {e}")
        return hashes

    def clear_cache(self) -> None:
        self._file_cache.clear()
        self._walk_cache.clear()