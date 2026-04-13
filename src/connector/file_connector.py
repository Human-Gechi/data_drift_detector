import pandas as pd

from pathlib import Path
import pandas as pd
from typing import Optional, List
from log import get_ingest_logger
import hashlib

data_logger = get_ingest_logger()
class DataFileLoader:
    DEFAULT_SEARCH_DIRS = [
        str(Path.home() / "Downloads"),
        str(Path.home() / "Documents"),
        str(Path.home() / "OneDrive/Desktop"),
        str(Path.home() / "Desktop"),
        str(Path.cwd())
    ]


    SUPPORTED_EXTENSIONS = {
        '.csv': pd.read_csv,
        '.json': pd.read_json,
        '.xlsx': pd.read_excel,
        '.xls': pd.read_excel,
        '.parquet': pd.read_parquet
    }

    def __init__(self, search_dirs: Optional[List[str]] = None):
        self.search_dirs = search_dirs or self.DEFAULT_SEARCH_DIRS
        self._cache = {}


    def is_virtualenv_folder(self, folder_path) -> bool:
        folder = Path(folder_path)
        if (folder.joinpath('Lib').is_dir() and
            folder.joinpath('Scripts').is_dir() and
            folder.joinpath('share').is_dir() and
            folder.joinpath('pyvenv.cfg').is_file()):
            return True

        if (folder.joinpath('bin').is_dir() and
            folder.joinpath('pyvenv.cfg').is_file()):
            return True
        return False

    def _walk_skip_venv(self, root: Path):
        try:
            for entry in root.iterdir():
                if entry.is_dir():
                    if self.is_virtualenv_folder(str(entry)):
                        continue
                    yield from self._walk_skip_venv(entry)
                else:
                    yield entry
        except PermissionError:
            pass

    def find(self, filename: str) -> Optional[Path]:
        """Find just one file"""
        if filename in self._cache:
            return self._cache[filename]

        for search_dir in self.search_dirs:
            path = Path(search_dir).expanduser().resolve()
            if not path.exists() or self.is_virtualenv_folder(str(path)):
                continue

            for file_path in self._walk_skip_venv(path):
                if file_path.name == filename:
                    self._cache[filename] = file_path
                    return file_path

        return None

    def find_all(self, extensions: Optional[List[str]] = None) -> List[Path]:
        """Find all files in a specific directory"""
        if extensions is None:
            extensions = list(self.SUPPORTED_EXTENSIONS.keys())

        files = []
        for search_dir in self.search_dirs:
            path = Path(search_dir).expanduser().resolve()
            if not path.exists() or self.is_virtualenv_folder(str(path)):
                continue

            for file_path in self._walk_skip_venv(path):
                if any(file_path.suffix == ext for ext in extensions):
                    files.append(file_path)

        return files

    def load(self, filename: str) -> Optional[pd.DataFrame]:
        """Find and load a file"""
        ext = Path(filename).suffix.lower()
        loader = self.SUPPORTED_EXTENSIONS.get(ext)

        if not loader:
            data_logger.warning(f"⚠️ Unsupported file type: {ext}")
            data_logger.warning(f"⚠️ Supported: {list(self.SUPPORTED_EXTENSIONS.keys())}")
            return None

        file_path = self.find(filename)

        if not file_path:
            data_logger.error(f"❌File not found: {filename}")
            data_logger.error(f"❌Searched in: {self.search_dirs}")
            return None


        try:
            df = loader(file_path)
            df = df.convert_dtypes()
            return df
        except Exception as e:
            data_logger.error(f"❌ Error loading {file_path}: {e}")
            return None
    def get_file_hash(self, file_path):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

#loader = DataFileLoader(search_dirs=[r"C:\Users\HP\data_lineage_visualizer"])

#df = loader.load("Product.csv")
#all_files = loader.find_all()
#print(f"Found {len(all_files)} data files")

#for file in all_files:
    #df = loader.load(file.name)
