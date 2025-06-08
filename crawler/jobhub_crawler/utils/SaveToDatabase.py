import json
import logging
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from jobhub_crawler.utils.helpers import _find_project_root, _find_folder, _find_latest_file
from jobhub_crawler.utils.notifier import _send_telegram_message


class SafeLogger:
    """Logger wrapper that handles Unicode characters safely on Windows"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.is_windows = sys.platform.startswith('win')

    def _safe_message(self, message: str) -> str:
        """Convert Unicode characters to safe ASCII representation on Windows"""
        if not self.is_windows:
            return message

        # Replace common Unicode characters with ASCII equivalents
        replacements = {
            '✅': '[SUCCESS]',
            '❌': '[FAILED]',
            '⚠️': '[WARNING]',
            '🎉': '[COMPLETE]',
            '💥': '[CRITICAL]',
            '📝': '[INFO]',
            '🔄': '[PROCESSING]'
        }

        for unicode_char, ascii_replacement in replacements.items():
            message = message.replace(unicode_char, ascii_replacement)

        return message

    def info(self, message: str):
        self.logger.info(self._safe_message(message))

    def warning(self, message: str):
        self.logger.warning(self._safe_message(message))

    def error(self, message: str):
        self.logger.error(self._safe_message(message))

    def debug(self, message: str):
        self.logger.debug(self._safe_message(message))


@dataclass
class APIConfig:
    """Configuration for API connection"""
    base_url: str
    csrf_token: str
    session_id: str
    timeout: int = 30
    max_retries: int = 3
    backoff_factor: float = 0.3


class JobDataManager:
    """Enhanced job data management with better error handling and performance"""

    def __init__(self, config: APIConfig):
        self.config = config
        self.session = self._create_session()
        raw_logger = self._setup_logging()
        self.logger = SafeLogger(raw_logger)

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        # Create formatters
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Create handlers
        file_handler = logging.FileHandler('job_manager.log', encoding='utf-8')
        file_handler.setFormatter(file_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)

        # Setup logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _create_session(self) -> requests.Session:
        """Create and configure requests session with retry strategy"""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set authentication cookies
        session.cookies.set("csrftoken", self.config.csrf_token)
        session.cookies.set("sessionid", self.config.session_id)

        # Set headers
        session.headers.update({
            "X-CSRFToken": self.config.csrf_token,
            "Content-Type": "application/json",
            "User-Agent": "JobHub-Crawler/1.0"
        })

        return session

    def get_existing_jobs(self) -> List[Dict]:
        """Fetch existing jobs from API"""
        try:
            response = self.session.get(
                self.config.base_url,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            jobs = response.json()
            self.logger.info(f"Found {len(jobs)} existing jobs")
            return jobs

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch existing jobs: {e}")
            return []

    def delete_job(self, job_id: int) -> bool:
        """Delete a single job by ID"""
        try:
            delete_url = f"{self.config.base_url}{job_id}/"
            response = self.session.delete(
                delete_url,
                timeout=self.config.timeout
            )

            if response.status_code == 204:
                self.logger.info(f"✅ Successfully deleted job ID {job_id}")
                return True
            else:
                self.logger.warning(f"❌ Failed to delete job ID {job_id}: HTTP {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error deleting job ID {job_id}: {e}")
            return False

    def delete_all_jobs(self) -> Tuple[int, int]:
        """Delete all existing jobs"""
        jobs = self.get_existing_jobs()
        if not jobs:
            self.logger.info("No jobs to delete")
            return 0, 0

        success_count = 0
        total_count = len(jobs)

        # Use ThreadPoolExecutor for concurrent deletions
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_job = {
                executor.submit(self.delete_job, job['id']): job['id']
                for job in jobs
            }

            for future in as_completed(future_to_job):
                if future.result():
                    success_count += 1

        self.logger.info(f"Deletion complete: {success_count}/{total_count} jobs deleted")
        return success_count, total_count

    def send_job_data(self, job_data: Dict) -> bool:
        """Send a single job data to API"""
        try:
            response = self.session.post(
                self.config.base_url,
                json=job_data,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send job data: {e}")
            if hasattr(e.response, 'text'):
                self.logger.error(f"Response: {e.response.text}")
            return False

    def batch_upload_jobs(self, jobs_data: List[Dict], batch_size: int = 10) -> Tuple[int, int]:
        """Upload jobs in batches with progress tracking"""
        total_jobs = len(jobs_data)
        success_count = 0

        self.logger.info(f"Starting upload of {total_jobs} jobs in batches of {batch_size}")

        for i in range(0, total_jobs, batch_size):
            batch = jobs_data[i:i + batch_size]
            batch_start = i + 1
            batch_end = min(i + batch_size, total_jobs)

            self.logger.info(f"Processing batch {batch_start}-{batch_end}/{total_jobs}")

            # Process batch with threading
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_job = {
                    executor.submit(self.send_job_data, job): job
                    for job in batch
                }

                for future in as_completed(future_to_job):
                    if future.result():
                        success_count += 1

            # Progress update
            progress = (batch_end / total_jobs) * 100
            self.logger.info(f"Progress: {success_count}/{batch_end} jobs uploaded ({progress:.1f}%)")

            # Brief pause between batches to avoid overwhelming the server
            if batch_end < total_jobs:
                time.sleep(0.5)

        self.logger.info(f"Upload complete: {success_count}/{total_jobs} jobs uploaded successfully")
        return success_count, total_jobs

    def load_jobs_from_file(self, file_path) -> Optional[List[Dict]]:
        """Load jobs data from JSON file with validation"""
        try:
            # Convert to Path object if it's a string
            if isinstance(file_path, str):
                file_path = Path(file_path)
            elif not isinstance(file_path, Path):
                file_path = Path(str(file_path))

            if not file_path.exists():
                self.logger.error(f"File not found: {file_path}")
                return None

            self.logger.info(f"Loading jobs from: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if 'jobs' not in data:
                self.logger.error("Invalid JSON structure: 'jobs' key not found")
                return None

            jobs = data['jobs']
            self.logger.info(f"📝 Loaded {len(jobs)} jobs from {file_path.name}")
            return jobs

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON format in {file_path}: {e}")
            return None
        except FileNotFoundError:
            self.logger.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"Error loading file {file_path}: {e}")
            return None

    def run_full_sync(self, data_file_path) -> bool:
        """Execute full synchronization process"""
        try:
            self.logger.info("🔄 Starting full job synchronization")

            # Convert to Path object if needed
            if isinstance(data_file_path, str):
                data_file_path = Path(data_file_path)

            # Step 1: Delete existing jobs
            deleted_count, total_existing = self.delete_all_jobs()

            # Step 2: Load new jobs data
            jobs_data = self.load_jobs_from_file(data_file_path)
            if not jobs_data:
                self.logger.error("Failed to load jobs data, aborting sync")
                return False

            # Step 3: Upload new jobs
            uploaded_count, total_new = self.batch_upload_jobs(jobs_data)

            # Summary
            self.logger.info("=" * 50)
            self.logger.info("SYNCHRONIZATION SUMMARY")
            self.logger.info(f"Deleted: {deleted_count}/{total_existing} existing jobs")
            self.logger.info(f"Uploaded: {uploaded_count}/{total_new} new jobs")
            self.logger.info(f"Success rate: {(uploaded_count / total_new) * 100:.1f}%")
            self.logger.info("=" * 50)

            return uploaded_count == total_new

        except Exception as e:
            self.logger.error(f"Critical error during synchronization: {e}")
            return False


def _SaveToData():
    """Main execution function"""
    try:
        # Initialize paths
        project_root = _find_project_root(Path(__file__))
        crawler_folder = _find_folder('crawler', search_dir=project_root)
        output_folder = _find_folder('output', search_dir=crawler_folder)
        latest_file = _find_latest_file(search_dir=output_folder, suffix='.json')

        # Debug information
        print(f"Debug - Project root: {project_root}")
        print(f"Debug - Crawler folder: {crawler_folder}")
        print(f"Debug - Output folder: {output_folder}")
        print(f"Debug - Latest file: {latest_file} (type: {type(latest_file)})")

        if not latest_file:
            print("❌ No JSON files found in output folder")
            return

        # Configuration
        config = APIConfig(
            base_url="http://127.0.0.1:8000/api/jobs/",
            csrf_token="AO6YCWxcc2iWvKody3CgZ4HHaN6RUbaS",
            session_id="k3b92xqdykakek2t66rnotctgu1wr4wy",
            timeout=30,
            max_retries=3
        )
        _send_telegram_message('', 'run sync database!', '', '', '')
        # Initialize manager and run sync
        manager = JobDataManager(config)
        success = manager.run_full_sync(latest_file)
        _send_telegram_message('', f'sync finished: {success}', '', '', '')

        if success:
            print("🎉 Job synchronization completed successfully!")
        else:
            print("⚠️ Job synchronization completed with some errors. Check logs for details.")

    except Exception as e:
        print(f"💥 Critical error: {e}")
        logging.error(f"Critical error in main: {e}")
        import traceback
        traceback.print_exc()


# if __name__ == '__main__':
#     # _SaveToData()
#     import tempfile
#
#     temp_dir = tempfile.gettempdir()
#     print(f"Đường dẫn TEMP của hệ thống là: {temp_dir}")