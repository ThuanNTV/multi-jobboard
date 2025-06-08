#!/usr/bin/env python3
"""
Selenium Cleanup Utility
Dọn dẹp các file temp và processes còn sót lại từ Selenium
"""

import os
import sys
import glob
import time
import shutil
import tempfile
import logging
import argparse
import psutil
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SeleniumCleaner:
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()

    def kill_browser_processes(self, force=False):
        """Kill tất cả browser processes"""
        browser_names = ['chrome', 'chromedriver', 'firefox', 'geckodriver', 'msedge', 'edgedriver']
        killed_count = 0

        logger.info("Scanning for browser processes...")

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_name = proc.info['name'].lower()

                # Check if it's a browser process
                if any(browser in proc_name for browser in browser_names):
                    if force:
                        # Force kill
                        proc.kill()
                        killed_count += 1
                        logger.info(f"Force killed: {proc.info['name']} (PID: {proc.info['pid']})")
                    else:
                        # Graceful termination
                        proc.terminate()
                        killed_count += 1
                        logger.info(f"Terminated: {proc.info['name']} (PID: {proc.info['pid']})")

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if killed_count == 0:
            logger.info("No browser processes found")
        else:
            logger.info(f"Total processes killed: {killed_count}")

        return killed_count

    def clean_selenium_temp_dirs(self):
        temp_root = tempfile.gettempdir()  # Lấy đường dẫn %TEMP%
        pattern = os.path.join(temp_root, "selenium_jobhub_*")
        temp_dirs = glob.glob(pattern)

        for dir_path in temp_dirs:
            if os.path.isdir(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    logger.info(f"🧹 Đã xoá thư mục: {dir_path}")
                except Exception as e:
                    logger.info(f"⚠️ Không thể xoá {dir_path}: {e}")

    def cleanup_temp_files(self, days_old=0):
        """Dọn dẹp temp files"""
        patterns = [
            'selenium_*',
            'selenium-*',
            'scoped_dir*',
            'chrome_debug_*',
            'chromedriver_*',
            '.com.google.Chrome*',
            'tmp*chrome*',
            'selenium_jobhub_*',
            'webdriver-*',
            'tmp*selenium*'
        ]

        cutoff_time = time.time() - (days_old * 24 * 60 * 60) if days_old > 0 else 0
        cleaned_count = 0
        total_size = 0

        logger.info(f"Cleaning temp files in: {self.temp_dir}")

        # First, let's scan the temp directory to see what's actually there
        logger.debug("Scanning temp directory contents...")
        try:
            all_items = os.listdir(self.temp_dir)
            selenium_items = [item for item in all_items if 'selenium' in item.lower()]
            chrome_items = [item for item in all_items if 'chrome' in item.lower()]

            if selenium_items:
                logger.info(f"Found {len(selenium_items)} selenium-related items")
                for item in selenium_items[:5]:  # Show first 5
                    logger.debug(f"  - {item}")

            if chrome_items:
                logger.info(f"Found {len(chrome_items)} chrome-related items")
                for item in chrome_items[:5]:  # Show first 5
                    logger.debug(f"  - {item}")

        except Exception as e:
            logger.warning(f"Could not scan temp directory: {e}")

        # Now clean using patterns
        for pattern in patterns:
            search_pattern = os.path.join(self.temp_dir, pattern)
            matched_items = glob.glob(search_pattern)

            if matched_items:
                logger.debug(f"Pattern '{pattern}' matched {len(matched_items)} items")

            for item_path in matched_items:
                try:
                    # Skip if item doesn't exist (might have been already deleted)
                    if not os.path.exists(item_path):
                        continue

                    # Check age if specified
                    if days_old > 0:
                        file_time = os.path.getmtime(item_path)
                        if file_time > cutoff_time:
                            logger.debug(f"Skipping {item_path} - too new")
                            continue

                    # Calculate size before deletion
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        os.unlink(item_path)
                        logger.debug(f"Removed file: {os.path.basename(item_path)} ({self._format_size(size)})")
                    elif os.path.isdir(item_path):
                        size = self._get_dir_size(item_path)
                        # Use more aggressive removal for stubborn directories
                        self._force_remove_directory(item_path)
                        logger.debug(f"Removed directory: {os.path.basename(item_path)} ({self._format_size(size)})")
                    else:
                        continue

                    total_size += size
                    cleaned_count += 1

                except (OSError, PermissionError) as e:
                    logger.warning(f"Could not remove {item_path}: {e}")
                    # Try alternative removal method for Windows
                    if os.name == 'nt':
                        try:
                            import subprocess
                            if os.path.isdir(item_path):
                                subprocess.run(['rmdir', '/s', '/q', item_path],
                                               shell=True, check=False,
                                               stdout=subprocess.DEVNULL,
                                               stderr=subprocess.DEVNULL)
                                logger.debug(f"Force removed directory with rmdir: {item_path}")
                        except:
                            pass

        # Additional cleanup for Windows-specific Chrome temp files
        if os.name == 'nt':
            self._cleanup_windows_chrome_temp()

        logger.info(f"Cleaned {cleaned_count} items, freed {self._format_size(total_size)}")
        return cleaned_count, total_size

    def cleanup_user_data_dirs(self):
        """Dọn dẹp Chrome user data directories cũ"""
        cleaned_count = 0
        total_size = 0

        # Common locations for Chrome user data
        possible_locations = [
            self.temp_dir,
            os.path.expanduser("~"),
            "/tmp" if os.name == 'posix' else None
        ]

        for location in possible_locations:
            if not location or not os.path.exists(location):
                continue

            # Look for Chrome user data directories
            chrome_dirs = glob.glob(os.path.join(location, "*chrome*", "User Data"))
            chrome_dirs.extend(glob.glob(os.path.join(location, "*Chrome*", "User Data")))

            for chrome_dir in chrome_dirs:
                if "selenium" in chrome_dir.lower() or "webdriver" in chrome_dir.lower():
                    try:
                        size = self._get_dir_size(chrome_dir)
                        shutil.rmtree(chrome_dir, ignore_errors=True)
                        total_size += size
                        cleaned_count += 1
                        logger.info(f"Removed Chrome user data: {chrome_dir}")
                    except Exception as e:
                        logger.warning(f"Could not remove {chrome_dir}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} Chrome user data dirs, freed {self._format_size(total_size)}")

        return cleaned_count, total_size

    def find_large_temp_files(self, min_size_mb=10):
        """Tìm các file temp lớn"""
        min_size = min_size_mb * 1024 * 1024  # Convert to bytes
        large_files = []

        logger.info(f"Scanning for temp files larger than {min_size_mb}MB...")

        try:
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(file_path)
                        if size > min_size:
                            large_files.append((file_path, size))
                    except (OSError, PermissionError):
                        continue

        except Exception as e:
            logger.error(f"Error scanning temp directory: {e}")

        # Sort by size (largest first)
        large_files.sort(key=lambda x: x[1], reverse=True)

        if large_files:
            logger.info(f"Found {len(large_files)} large temp files:")
            for file_path, size in large_files[:10]:  # Show top 10
                logger.info(f"  {self._format_size(size)}: {file_path}")
        else:
            logger.info("No large temp files found")

        return large_files

    def _get_dir_size(self, path):
        """Calculate directory size"""
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        continue
        except Exception:
            pass
        return total_size

    def _format_size(self, size_bytes):
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def emergency_cleanup(self):
        """Emergency cleanup - kill all và xóa tất cả"""
        logger.info("🚨 EMERGENCY CLEANUP STARTED 🚨")

        # 1. Force kill all browser processes
        killed = self.kill_browser_processes(force=True)

        # 2. Wait a bit for processes to die
        if killed > 0:
            logger.info("Waiting for processes to terminate...")
            time.sleep(3)

        # 3. Clean temp files
        cleaned_files, freed_space = self.cleanup_temp_files()

        # 4. Clean user data directories
        cleaned_dirs, freed_space2 = self.cleanup_user_data_dirs()

        total_freed = freed_space + freed_space2

        logger.info("🎉 EMERGENCY CLEANUP COMPLETED 🎉")
        logger.info(f"Total freed space: {self._format_size(total_freed)}")

        return {
            'processes_killed': killed,
            'files_cleaned': cleaned_files,
            'dirs_cleaned': cleaned_dirs,
            'space_freed': total_freed
        }

    def _cleanup_windows_chrome_temp(self):
        """Additional cleanup cho Windows Chrome temp files"""
        if os.name != 'nt':
            return

        try:
            # Chrome creates temp files in various locations
            additional_patterns = [
                os.path.join(self.temp_dir, '*.tmp'),
                os.path.join(self.temp_dir, 'chrome_*'),
                os.path.join(self.temp_dir, 'Crashpad', '*'),
            ]

            for pattern in additional_patterns:
                for item in glob.glob(pattern):
                    try:
                        if os.path.isfile(item):
                            os.unlink(item)
                        elif os.path.isdir(item):
                            self._force_remove_directory(item)
                    except:
                        pass

        except Exception as e:
            logger.debug(f"Error in Windows Chrome cleanup: {e}")

    def _force_remove_directory(self, path):
        """Force remove directory with multiple strategies"""
        try:
            # Strategy 1: Standard shutil.rmtree
            shutil.rmtree(path, ignore_errors=False)
            return True
        except Exception:
            pass

        try:
            # Strategy 2: Change permissions and retry
            if os.name == 'nt':  # Windows
                import stat
                def handle_remove_readonly(func, path, exc):
                    if os.path.exists(path):
                        os.chmod(path, stat.S_IWRITE)
                        func(path)

                shutil.rmtree(path, onerror=handle_remove_readonly)
                return True
            else:  # Unix-like
                import subprocess
                subprocess.run(['rm', '-rf', path], check=True)
                return True
        except Exception:
            pass

        try:
            # Strategy 3: Use system commands (Windows)
            if os.name == 'nt':
                import subprocess
                result = subprocess.run(['rmdir', '/s', '/q', path],
                                        shell=True, capture_output=True)
                return result.returncode == 0
        except Exception:
            pass

        return False

    def cleanup_specific_folder(self, folder_name):
        """Cleanup một folder cụ thể"""
        folder_path = os.path.join(self.temp_dir, folder_name)

        if not os.path.exists(folder_path):
            logger.warning(f"Folder not found: {folder_path}")
            return False

        try:
            size = self._get_dir_size(folder_path)
            success = self._force_remove_directory(folder_path)

            if success:
                logger.info(f"Successfully removed: {folder_name} ({self._format_size(size)})")
                return True
            else:
                logger.error(f"Failed to remove: {folder_name}")
                return False

        except Exception as e:
            logger.error(f"Error removing {folder_name}: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Selenium Cleanup Utility')
    parser.add_argument('--emergency', action='store_true',
                        help='Emergency cleanup - kill all browsers and clean everything')
    parser.add_argument('--kill-processes', action='store_true',
                        help='Kill browser processes only')
    parser.add_argument('--clean-temp', action='store_true',
                        help='Clean temp files only')
    parser.add_argument('--find-large', type=int, default=0, metavar='MB',
                        help='Find temp files larger than specified MB')
    parser.add_argument('--days-old', type=int, default=0,
                        help='Only clean files older than specified days')
    parser.add_argument('--force', action='store_true',
                        help='Force kill processes (use with --kill-processes)')

    args = parser.parse_args()

    cleaner = SeleniumCleaner()

    if args.emergency:
        result = cleaner.emergency_cleanup()
        print(f"\nResults:")
        print(f"Processes killed: {result['processes_killed']}")
        print(f"Files cleaned: {result['files_cleaned']}")
        print(f"Directories cleaned: {result['dirs_cleaned']}")
        print(f"Space freed: {cleaner._format_size(result['space_freed'])}")

    elif args.kill_processes:
        cleaner.kill_browser_processes(force=args.force)

    elif args.clean_temp:
        cleaner.cleanup_temp_files(days_old=args.days_old)

    elif args.find_large > 0:
        large_files = cleaner.find_large_temp_files(min_size_mb=args.find_large)
        if large_files:
            response = input(f"\nFound {len(large_files)} large files. Delete them? (y/N): ")
            if response.lower() == 'y':
                deleted_count = 0
                freed_space = 0
                for file_path, size in large_files:
                    try:
                        os.unlink(file_path)
                        deleted_count += 1
                        freed_space += size
                        logger.info(f"Deleted: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not delete {file_path}: {e}")

                logger.info(f"Deleted {deleted_count} files, freed {cleaner._format_size(freed_space)}")
    else:
        # Default: show help
        parser.print_help()


if __name__ == "__main__":
    main()
