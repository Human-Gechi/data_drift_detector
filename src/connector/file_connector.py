import pandas as pd

from pathlib import Path
import pandas as pd
from typing import Optional, List
from log import get_ingest_logger

data_logger = get_ingest_logger()
class DataFileLoader:
    DEFAULT_SEARCH_DIRS = [
        str(Path.home() / "Downloads"),
        str(Path.home() / "Documents"),
        str(Path.home() / "OneDrive/Desktop"),
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

    def find(self, filename: str) -> Optional[Path]:
        """Find file in search directories"""
        if filename in self._cache:
            return self._cache[filename]

        for search_dir in self.search_dirs:
            path = Path(search_dir).expanduser().resolve()

            if not path.exists():
                continue

            # Quick search
            for file_path in path.rglob(filename):
                self._cache[filename] = file_path
                return file_path

        return None

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
            data_logger.info(f"✅ Loaded: {file_path}")
            data_logger.info(f"Shape: {df.shape}")
            data_logger.info(f"Columns: {list(df.columns[:5])}...")
            return df
        except Exception as e:
            data_logger.error(f"❌ Error loading {file_path}: {e}")
            return None

    def find_all(self, extensions: Optional[List[str]] = None) -> List[Path]:
        """Find all files with given extensions"""
        if extensions is None:
            extensions = list(self.SUPPORTED_EXTENSIONS.keys())

        files = []
        for search_dir in self.search_dirs:
            path = Path(search_dir).expanduser().resolve()

            if not path.exists():
                continue

            for ext in extensions:
                files.extend(path.rglob(f"*{ext}"))

        return files



loader = DataFileLoader()

df = loader.load("Products.c")

all_files = loader.find_all()
print(f"Found {len(all_files)} data files")

for file in all_files[-5:-1]:
    df = loader.load(file.name)