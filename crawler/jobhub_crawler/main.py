from jobhub_crawler.core.job_runner import JobRunner
from spiders.topdev import TopDevSpider

# from selenium_crawler.spiders.itviec import ItViecSpider
# from selenium_crawler.spiders.vietnamworks import VietnamworksSpider


if __name__ == "__main__":
    runner = JobRunner()
    runner.run_all([
        TopDevSpider,
        # ItViecSpider,
        # VietnamworksSpider
    ])
    file_path = runner.save_results()
    print(f"Kết quả đã được lưu tại: {file_path}")