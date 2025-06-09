// Pagination state
let currentPage = 1;
let totalPages = 1;
const itemsPerPage = 20;
let allJobs = []; // This will hold all job data

// Fetch jobs from Django API
async function fetchJobs() {
  try {
    const response = await fetch("http://127.0.0.1:8000/api/jobs/", {
      method: "GET",
      mode: "cors",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    // Django REST Framework với pagination sẽ trả về object có structure:
    // { count, next, previous, results }
    // Nếu không có pagination thì trả về array trực tiếp

    if (Array.isArray(data)) {
      // API trả về array trực tiếp (không có pagination)
      allJobs = data;
      totalPages = Math.ceil(allJobs.length / itemsPerPage);
    } else if (data.results && Array.isArray(data.results)) {
      // API có pagination
      allJobs = data.results;
      totalPages = Math.ceil(data.count / itemsPerPage);
    } else {
      console.error("Unexpected API response structure:", data);
      return;
    }

    // Load first page
    updatePagination();
    loadJobsForPage(1);
  } catch (error) {
    console.error("Fetch error:", error);

    // Show error message to user
    const jobList = document.getElementById("jobList");
    jobList.innerHTML = `
          <div class="error-message" style="text-align: center; padding: 2rem; color: #e74c3c;">
            <h3>Không thể tải dữ liệu việc làm</h3>
            <p>Lỗi: ${error.message}</p>
            <button onclick="fetchJobs()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
              Thử lại
            </button>
          </div>
        `;
  }
}

function goToPage(page) {
  if (page < 1 || page > totalPages) return;

  currentPage = page;
  updatePagination();
  loadJobsForPage(page);

  // Smooth scroll to top of job list
  const jobListElement = document.querySelector(".job-list");
  if (jobListElement) {
    jobListElement.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }
}

function nextPage() {
  if (currentPage < totalPages) {
    goToPage(currentPage + 1);
  }
}

function previousPage() {
  if (currentPage > 1) {
    goToPage(currentPage - 1);
  }
}

function updatePagination() {
  // Update pagination buttons
  const buttons = document.querySelectorAll(
    ".pagination-btn:not(.pagination-prev):not(.pagination-next)"
  );
  buttons.forEach((btn) => {
    btn.classList.remove("active");
    if (parseInt(btn.textContent) === currentPage) {
      btn.classList.add("active");
    }
  });

  // Update prev/next buttons
  const prevBtn = document.querySelector(".pagination-prev");
  const nextBtn = document.querySelector(".pagination-next");

  if (prevBtn) prevBtn.disabled = currentPage === 1;
  if (nextBtn) nextBtn.disabled = currentPage === totalPages;

  // Update pagination info
  const paginationInfo = document.querySelector(".pagination-info");
  if (paginationInfo) {
    paginationInfo.textContent = `Trang ${currentPage} / ${totalPages}`;
  }

  // Update results count
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, allJobs.length);
  const resultsCount = document.querySelector(".results-count");
  if (resultsCount) {
    resultsCount.innerHTML = `Hiển thị <span class="highlight">${startItem}-${endItem}</span> trong tổng số <span class="highlight">${allJobs.length}</span> việc làm`;
  }
}

function loadJobsForPage(page) {
  const jobList = document.getElementById("jobList");
  if (!jobList) {
    console.error("Job list element not found");
    return;
  }

  const startIndex = (page - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const jobsToShow = allJobs.slice(startIndex, endIndex);

  // Add loading state
  jobList.classList.add("loading");

  setTimeout(() => {
    jobList.innerHTML = "";

    if (jobsToShow.length === 0) {
      jobList.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: #7f8c8d;">
              <h3>Không có việc làm nào</h3>
              <p>Hãy thử tìm kiếm với từ khóa khác.</p>
            </div>
          `;
    } else {
      jobsToShow.forEach((job, index) => {
        const jobItem = document.createElement("li");
        jobItem.className = "job-item";
        jobItem.style.animationDelay = `${index * 0.1}s`;

        // Handle các field có thể null/undefined
        const title = job.title || "Không có tiêu đề";
        const company = job.company || "Không rõ công ty";
        let salary = job.salary || "Thương lượng";
        if (salary === "Sign in to view salary") {
          const minSalary = 7000000;
          const maxSalary = 15000000;
          const randomSalary =
            Math.floor(Math.random() * ((maxSalary - minSalary) / 500000 + 1)) *
              500000 +
            minSalary;
          salary = `${randomSalary.toLocaleString("vi-VN")} VNĐ`;
        }
        const location = job.location || [];
        // Chuyển location thành chuỗi nếu là mảng
        const locationsHtml = location
          .filter((location) => location && location.trim() !== "") // lọc bỏ tag null, undefined, hoặc chỉ có khoảng trắng
          .map((location) => `<span class="location">📍${location}</span>`)
          .join("");

        const tags = job.tags || [];
        const tagsHtml = tags
          .filter((tag) => tag && tag.trim() !== "") // lọc bỏ tag null, undefined, hoặc chỉ có khoảng trắng
          .map((tag) => `<span class="tag">${tag}</span>`)
          .join("");
        jobItem.innerHTML = `
              <div class="job-info">
                <a href="job.html?id=${job.id}" class="job-link">
                <div class="job-title">${title}</div>
                <div class="job-company">Company: ${company}</div>
                <div class="job-meta">
                  <span class="job-salary">${salary}</span>
                  <span class="job-location">${locationsHtml}</span>
                </div>
                <div class="job-tags">${tagsHtml}</div>
              </div>
              <a class="apply-btn" href="job.html?id=${job.id}">Xem chi tiết</a>
              </a>
            `;

        jobList.appendChild(jobItem);
      });
    }

    // Remove loading state
    jobList.classList.remove("loading");
  }, 300);
}

//   function applyJob(jobId) {
//     alert(`Ứng tuyển vào job ID: ${jobId}`);
//     // Implement application logic here
// }

function sortJobs(sortBy) {
  const jobList = document.getElementById("jobList");
  if (jobList) {
    jobList.classList.add("loading");
  }

  setTimeout(() => {
    // Implement sorting logic
    switch (sortBy) {
      case "newest":
        allJobs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        break;
      case "oldest":
        allJobs.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        break;
      case "salary_high":
        allJobs.sort((a, b) => {
          const salarya = parseInt(a.salary?.replace(/\D/g, "") || "0");
          const salaryb = parseInt(b.salary?.replace(/\D/g, "") || "0");
          return salaryb - salarya;
        });
        break;
      case "salary_low":
        allJobs.sort((a, b) => {
          const salarya = parseInt(a.salary?.replace(/\D/g, "") || "0");
          const salaryb = parseInt(b.salary?.replace(/\D/g, "") || "0");
          return salarya - salaryb;
        });
        break;
    }

    // Reset to first page after sorting
    currentPage = 1;
    totalPages = Math.ceil(allJobs.length / itemsPerPage);
    updatePagination();
    loadJobsForPage(1);
  }, 300);
}

// Add search functionality
function initializeSearch() {
  const searchBtn = document.querySelector(".search-bar button");
  const searchInput = document.querySelector(".search-bar input");

  if (searchBtn) {
    searchBtn.addEventListener("click", performSearch);
  }

  if (searchInput) {
    searchInput.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        performSearch();
      }
    });
  }
}

function performSearch() {
  const keyword = document.querySelector(".search-bar input")?.value || "";
  const location = document.querySelector(".search-bar select")?.value || "";

  if (keyword || location) {
    console.log("Searching for:", keyword, "in", location);

    // Filter jobs based on search criteria
    let filteredJobs = [...allJobs]; // Copy original array

    if (keyword) {
      filteredJobs = filteredJobs.filter(
        (job) =>
          job.title?.toLowerCase().includes(keyword.toLowerCase()) ||
          job.company?.toLowerCase().includes(keyword.toLowerCase()) ||
          job.tags?.toLowerCase().includes(keyword.toLowerCase()) ||
          job.description?.toLowerCase().includes(keyword.toLowerCase())
      );
    }

    if (location) {
      filteredJobs = filteredJobs.filter((job) =>
        job.location?.toLowerCase().includes(location.toLowerCase())
      );
    }

    // Update display with filtered results
    allJobs = filteredJobs;
    totalPages = Math.ceil(allJobs.length / itemsPerPage);
    currentPage = 1;
    updatePagination();
    loadJobsForPage(1);
  }
}

// Initialize everything when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  console.log("DOM loaded, fetching jobs...");
  fetchJobs();
  initializeSearch();
});

// Also run if script is loaded after DOM
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () {
    console.log("DOM loaded, fetching jobs...");
    fetchJobs();
    initializeSearch();
  });
} else {
  console.log("DOM already loaded, fetching jobs...");
  fetchJobs();
  initializeSearch();
}
