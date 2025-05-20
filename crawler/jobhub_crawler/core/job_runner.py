import threading
import json
import logging
import os
import time
from datetime import datetime
from typing import List, Type, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from jobhub_crawler.core.job_item import JobItem


class JobRunner:
    """
    JobRunner handles the concurrent execution of multiple job spiders
    and consolidates their results into a single output.
    """

    def __init__(self, output_dir: str = "output", log_level: int = logging.INFO):
        """
        Initialize the JobRunner

        Args:
            output_dir: Directory to save output files
            log_level: Logging level (e.g., logging.INFO, logging.DEBUG)
        """
        self.jobs: List[JobItem] = []
        self.lock = threading.Lock()
        self.output_dir = output_dir
        self.start_time = None
        self.end_time = None

        # Configure root logger first to ensure all loggers display to console
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear any existing handlers to avoid duplicate logs
        if root_logger.handlers:
            for handler in root_logger.handlers:
                root_logger.removeHandler(handler)

        # Add console handler to root logger
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Set up this class's logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        # Force immediate output (disable buffering)
        console_handler.setLevel(log_level)

        # Add a simple test log to verify logging is working
        self.logger.info("JobRunner initialized - logging is active")

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.logger.info(f"Created output directory: {output_dir}")

    def run_spider(self, spider_class: Type) -> List[JobItem]:
        """
        Run a single spider and return its results

        Args:
            spider_class: The spider class to instantiate and run

        Returns:
            List of JobItem objects collected by the spider
        """
        spider_name = spider_class.__name__
        self.logger.info(f"Starting spider: {spider_name}")

        try:
            spider = spider_class()
            jobs = spider.run()  # Assuming updated spider.run() returns the jobs list

            if jobs:
                self.logger.info(f"Spider {spider_name} collected {len(jobs)} jobs")
                with self.lock:
                    self.jobs.extend(jobs)
                return jobs
            else:
                self.logger.warning(f"Spider {spider_name} did not collect any jobs")
                return []

        except Exception as e:
            self.logger.error(f"Error running spider {spider_name}: {str(e)}")
            return []

    def run_all(self, spiders: List[Type], max_workers: Optional[int] = None, timeout: Optional[int] = None) -> List[
        JobItem]:
        """
        Run all spiders concurrently using a thread pool

        Args:
            spiders: List of spider classes to run
            max_workers: Maximum number of concurrent threads (default: number of spiders)
            timeout: Maximum time in seconds to wait for all spiders (default: None, wait indefinitely)

        Returns:
            List of all collected JobItem objects
        """
        self.start_time = time.time()
        self.logger.info(f"Starting job runner with {len(spiders)} spiders")

        # Use ThreadPoolExecutor for better thread management
        max_workers = max_workers or len(spiders)
        self.logger.info(f"Using thread pool with {max_workers} workers")

        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all spiders to the executor
            future_to_spider = {
                executor.submit(self.run_spider, spider): spider.__name__
                for spider in spiders
            }

            # Process results as they complete
            for future in as_completed(future_to_spider, timeout=timeout):
                spider_name = future_to_spider[future]
                try:
                    spider_jobs = future.result()
                    results[spider_name] = len(spider_jobs)
                except Exception as e:
                    self.logger.error(f"Spider {spider_name} generated an exception: {str(e)}")

        self.end_time = time.time()
        duration = self.end_time - self.start_time
        self.logger.info(f"All spiders completed in {duration:.2f} seconds")
        self.logger.info(f"Results summary: {results}")
        self.logger.info(f"Total jobs collected: {len(self.jobs)}")

        return self.jobs

    def save_results(self, filename: Optional[str] = None) -> str:
        """
        Save collected jobs to a JSON file

        Args:
            filename: Optional filename override

        Returns:
            Path to the saved file
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jobs_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        # Convert jobs to dictionaries
        data = [job.to_dict() for job in self.jobs]

        # Add metadata
        metadata = {
            "total_jobs": len(data),
            "created_at": datetime.now().isoformat(),
            "execution_time": self.end_time - self.start_time if self.end_time and self.start_time else None,
            "sources": self._get_job_sources()
        }

        output = {
            "metadata": metadata,
            "jobs": data
        }

        # Write to file
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Saved {len(data)} jobs to {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error saving results to {filepath}: {str(e)}")
            return ""

    def _get_job_sources(self) -> Dict[str, int]:
        """
        Count jobs by source

        Returns:
            Dictionary mapping source names to job counts
        """
        sources = {}
        for job in self.jobs:
            sources[job.source] = sources.get(job.source, 0) + 1
        return sources

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collected jobs

        Returns:
            Dictionary with job statistics
        """
        if not self.jobs:
            return {"total_jobs": 0}

        stats = {
            "total_jobs": len(self.jobs),
            "sources": self._get_job_sources(),
            "execution_time": self.end_time - self.start_time if self.end_time and self.start_time else None
        }

        # Count unique companies
        companies = set(job.company for job in self.jobs if job.company)
        stats["unique_companies"] = len(companies)

        # Count unique locations
        locations = set(job.location for job in self.jobs if job.location)
        stats["unique_locations"] = len(locations)

        # Get top tags
        all_tags = []
        for job in self.jobs:
            all_tags.extend(job.tags or [])

        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Get top 10 tags
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        stats["top_tags"] = dict(top_tags)

        return stats