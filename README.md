# Data Drift Detector for Production Datasets

**Description:**
A tool to monitor production datasets (CSV, Parquet, or database tables) and automatically detect data drift—unexpected changes in data distributions, value ranges, or categorical values. The tool alerts users when new data deviates from historical baselines, helping maintain model reliability and data quality.

**Key Features:**
- Profiles and stores baseline statistics for each column
- Periodically monitors and compares new data to baselines
- Detects drift using statistical tests (KS test, chi-square, etc.)
- Generates alerts and summary reports when drift is detected
- Visualizes data distributions and drift trends over time
- Supports CSV, Parquet, and database tables
- Configurable thresholds for drift sensitivity

**Why use it?**
Ensure data consistency, catch issues early, and maintain trust in analytics and machine learning systems.