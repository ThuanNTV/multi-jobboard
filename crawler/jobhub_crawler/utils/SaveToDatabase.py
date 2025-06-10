import json
import logging
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
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
            '🔄': '[PROCESSING]',
            '💾': '[SAVE]',
            '🔍': '[SEARCH]'
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

    def critical(self, message: str):
        self.logger.critical(self._safe_message(message))


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
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )

        # Create handlers
        file_handler = logging.FileHandler('job_manager.log', encoding='utf-8')
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.INFO)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging.INFO)

        # Setup logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()
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
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
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
            "User-Agent": "JobHub-Crawler/1.0",
            "Accept": "application/json",
            "Referer": self.config.base_url
        })

        return session

    def get_existing_jobs(self) -> List[Dict]:
        """Fetch existing jobs from API with pagination support"""
        all_jobs = []
        page = 1

        try:
            while True:
                params = {'page': page, 'limit': 100}  # Adjust limit as needed
                response = self.session.get(
                    self.config.base_url,
                    params=params,
                    timeout=self.config.timeout
                )
                response.raise_for_status()

                data = response.json()

                # Handle different response formats
                if isinstance(data, list):
                    jobs = data
                    has_more = len(jobs) == 100  # Assume no more if less than limit
                elif isinstance(data, dict):
                    jobs = data.get('results', data.get('jobs', []))
                    has_more = data.get('next') is not None
                else:
                    jobs = []
                    has_more = False

                all_jobs.extend(jobs)

                if not has_more or not jobs:
                    break

                page += 1

            self.logger.info(f"🔍 Found {len(all_jobs)} existing jobs")
            return all_jobs

        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Failed to fetch existing jobs: {e}")
            return []

    def delete_job(self, job_id: int) -> bool:
        """Delete a single job by ID"""
        try:
            delete_url = f"{self.config.base_url.rstrip('/')}/{job_id}/"
            response = self.session.delete(
                delete_url,
                timeout=self.config.timeout
            )

            if response.status_code in [204, 200]:
                self.logger.debug(f"✅ Successfully deleted job ID {job_id}")
                return True
            else:
                self.logger.warning(
                    f"❌ Failed to delete job ID {job_id}: HTTP {response.status_code}"
                )
                return False

        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Error deleting job ID {job_id}: {e}")
            return False

    def delete_all_jobs(self) -> Tuple[int, int]:
        """Delete all existing jobs"""
        jobs = self.get_existing_jobs()
        if not jobs:
            self.logger.info("📝 No jobs to delete")
            return 0, 0

        success_count = 0
        total_count = len(jobs)

        self.logger.info(f"🔄 Starting deletion of {total_count} jobs")

        # Use ThreadPoolExecutor for concurrent deletions
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_job = {
                executor.submit(self.delete_job, job['id']): job['id']
                for job in jobs
            }

            for future in as_completed(future_to_job):
                if future.result():
                    success_count += 1

                # Progress update every 10 deletions
                if success_count % 10 == 0:
                    progress = (success_count / total_count) * 100
                    self.logger.info(f"Deletion progress: {success_count}/{total_count} ({progress:.1f}%)")

        self.logger.info(f"🎉 Deletion complete: {success_count}/{total_count} jobs deleted")
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
            self.logger.debug(f"✅ Successfully uploaded job: {job_data.get('title', 'Unknown')}")
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"❌ Failed to send job data: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response status: {e.response.status_code}")
                self.logger.error(f"Response text: {e.response.text[:500]}...")
            return False

    def batch_upload_jobs(self, jobs_data: List[Dict], batch_size: int = 10) -> Tuple[int, int]:
        """Upload jobs in batches with progress tracking"""
        if not jobs_data:
            self.logger.warning("⚠️ No jobs to upload")
            return 0, 0

        total_jobs = len(jobs_data)
        success_count = 0

        self.logger.info(f"🔄 Starting upload of {total_jobs} jobs in batches of {batch_size}")

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

        self.logger.info(f"🎉 Upload complete: {success_count}/{total_jobs} jobs uploaded successfully")
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
                self.logger.error(f"❌ File not found: {file_path}")
                return None

            self.logger.info(f"📝 Loading jobs from: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                jobs = data
            elif isinstance(data, dict):
                jobs = data.get('jobs', data.get('results', []))
            else:
                self.logger.error("❌ Invalid JSON structure: expected list or dict with 'jobs'/'results' key")
                return None

            if not jobs:
                self.logger.warning("⚠️ No jobs found in the file")
                return []

            self.logger.info(f"📝 Loaded {len(jobs)} jobs from {file_path.name}")
            return jobs

        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Invalid JSON format in {file_path}: {e}")
            return None
        except FileNotFoundError:
            self.logger.error(f"❌ File not found: {file_path}")
            return None
        except Exception as e:
            self.logger.error(f"❌ Error loading file {file_path}: {e}")
            return None

    def find_duplicate_jobs(self, existing_jobs: List[Dict], new_jobs: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Find duplicate and unique jobs based on company and company_url_img"""
        unique_jobs = []
        duplicate_jobs = []

        # Create a set of existing job signatures for faster lookup
        existing_signatures = {
            (job.get('company', ''), job.get('company_url_img', ''))
            for job in existing_jobs
        }

        for new_job in new_jobs:
            job_signature = (new_job.get('company', ''), new_job.get('company_url_img', ''))

            if job_signature in existing_signatures:
                duplicate_jobs.append(new_job)
                self.logger.debug(
                    f"Duplicate job found: {new_job.get('title', 'Unknown')} - {new_job.get('company', 'Unknown')}")
            else:
                unique_jobs.append(new_job)

        self.logger.info(f"🔍 Found {len(unique_jobs)} unique jobs and {len(duplicate_jobs)} duplicates")
        return unique_jobs, duplicate_jobs

    def sync_jobs_incrementally(self, data_file_path) -> bool:
        """Synchronize jobs incrementally (only add new jobs, don't delete existing ones)"""
        try:
            self.logger.info("🔄 Starting incremental job synchronization")

            # Convert to Path object if needed
            if isinstance(data_file_path, str):
                data_file_path = Path(data_file_path)

            # Step 1: Get existing jobs
            existing_jobs = self.get_existing_jobs()

            # Step 2: Load new jobs data
            new_jobs_data = self.load_jobs_from_file(data_file_path)
            if new_jobs_data is None:
                self.logger.error("❌ Failed to load jobs data, aborting sync")
                return False

            # Step 3: Find unique jobs
            unique_jobs, duplicate_jobs = self.find_duplicate_jobs(existing_jobs, new_jobs_data)

            if not unique_jobs:
                self.logger.info("📝 No new jobs to upload. All jobs already exist.")
                return True

            # Step 4: Upload unique jobs
            uploaded_count, total_unique = self.batch_upload_jobs(unique_jobs)

            # Summary
            self.logger.info("=" * 60)
            self.logger.info("INCREMENTAL SYNCHRONIZATION SUMMARY")
            self.logger.info(f"Existing jobs: {len(existing_jobs)}")
            self.logger.info(f"New jobs from file: {len(new_jobs_data)}")
            self.logger.info(f"Duplicate jobs (skipped): {len(duplicate_jobs)}")
            self.logger.info(f"Unique jobs found: {len(unique_jobs)}")
            self.logger.info(f"Successfully uploaded: {uploaded_count}/{total_unique}")
            if total_unique > 0:
                self.logger.info(f"Success rate: {(uploaded_count / total_unique) * 100:.1f}%")
            self.logger.info("=" * 60)

            return uploaded_count == total_unique

        except Exception as e:
            self.logger.critical(f"💥 Critical error during incremental synchronization: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_full_sync(self, data_file_path) -> bool:
        """Execute full synchronization process (delete all + upload new)"""
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
                self.logger.error("❌ Failed to load jobs data, aborting sync")
                return False

            # Step 3: Upload new jobs
            uploaded_count, total_new = self.batch_upload_jobs(jobs_data)

            # Summary
            self.logger.info("=" * 60)
            self.logger.info("FULL SYNCHRONIZATION SUMMARY")
            self.logger.info(f"Deleted: {deleted_count}/{total_existing} existing jobs")
            self.logger.info(f"Uploaded: {uploaded_count}/{total_new} new jobs")
            if total_new > 0:
                self.logger.info(f"Success rate: {(uploaded_count / total_new) * 100:.1f}%")
            self.logger.info("=" * 60)

            return uploaded_count == total_new

        except Exception as e:
            self.logger.critical(f"💥 Critical error during full synchronization: {e}")
            import traceback
            traceback.print_exc()
            return False


def save_to_database(sync_type: str = "incremental"):
    """
    Main execution function

    Args:
        sync_type: "incremental" for adding only new jobs, "full" for complete replacement
    """
    try:
        # Initialize paths
        project_root = _find_project_root(Path(__file__))
        crawler_folder = _find_folder('crawler', search_dir=project_root)
        output_folder = _find_folder('output', search_dir=crawler_folder)
        latest_file = _find_latest_file(search_dir=output_folder, suffix='.json')

        if not latest_file:
            print("❌ No JSON files found in output folder")
            return False

        # Configuration
        config = APIConfig(
            base_url="http://127.0.0.1:8000/api/jobs/",
            csrf_token="5tZGjul5LYJcAAzPnLvuLATBfBh30KYq",
            session_id="qtsdon9m6q8uzcya7q2h4d8goavqvhc2",
            timeout=30,
            max_retries=3
        )

        # Send notification
        _send_telegram_message('', f'Starting {sync_type} database sync!', '', '', '')

        # Initialize manager and run sync
        manager = JobDataManager(config)

        if sync_type.lower() == "full":
            success = manager.run_full_sync(latest_file)
        else:
            success = manager.sync_jobs_incrementally(latest_file)

        # Send completion notification
        status = "successfully" if success else "with errors"
        _send_telegram_message('', f'{sync_type.title()} sync finished {status}!', '', '', '')

        if success:
            print(f"🎉 {sync_type.title()} job synchronization completed successfully!")
        else:
            print(f"⚠️ {sync_type.title()} job synchronization completed with some errors. Check logs for details.")

        return success

    except Exception as e:
        error_msg = f"💥 Critical error: {e}"
        print(error_msg)
        logging.error(f"Critical error in save_to_database: {e}")
        _send_telegram_message('', f'Database sync failed: {str(e)}', '', '', '')
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point with improved error handling"""
    try:
        # Initialize paths
        project_root = _find_project_root(Path(__file__))
        crawler_folder = _find_folder('crawler', search_dir=project_root)
        output_folder = _find_folder('output', search_dir=crawler_folder)
        latest_file = _find_latest_file(search_dir=output_folder, suffix='.json')

        if not latest_file:
            print("❌ No JSON files found in output folder")
            return

        # Configuration
        config = APIConfig(
            base_url="http://127.0.0.1:8000/api/jobs/",
            csrf_token="5tZGjul5LYJcAAzPnLvuLATBfBh30KYq",
            session_id="qtsdon9m6q8uzcya7q2h4d8goavqvhc2",
            timeout=30,
            max_retries=3
        )

        # Initialize manager
        manager = JobDataManager(config)

        # Get existing jobs
        existing_jobs = manager.get_existing_jobs()

        # Load new jobs
        new_jobs_data = manager.load_jobs_from_file(latest_file)
        if not new_jobs_data:
            manager.logger.error("❌ Failed to load jobs data")
            return

        # Find unique jobs
        unique_jobs, duplicate_jobs = manager.find_duplicate_jobs(existing_jobs, new_jobs_data)

        if unique_jobs:
            print(f"💾 Found {len(unique_jobs)} new jobs to save")
            success_count, total_count = manager.batch_upload_jobs(unique_jobs)

            if success_count == total_count:
                print("🎉 All new jobs saved successfully!")
            else:
                print(f"⚠️ Saved {success_count}/{total_count} jobs")
        else:
            print("📝 All jobs already exist in database!")

    except Exception as e:
        print(f"💥 Critical error in main: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # Example usage:
    # For incremental sync (recommended):
    save_to_database("incremental")

    # For full sync (replace all data):
    # save_to_database("full")

    # For manual testing:
    # main()