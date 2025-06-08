const jobDetailEl = document.getElementById("job-detail");

// Lấy ID từ URL
const urlParams = new URLSearchParams(window.location.search);
const jobId = urlParams.get("id");

if (!jobId) {
  jobDetailEl.innerHTML = "<p>Không tìm thấy công việc.</p>";
  throw new Error("Missing job ID in URL");
}

// Advanced text formatting function - không cần OpenAI API
function formatJobDescription(rawText) {
  if (!rawText) return "<p>Không có mô tả.</p>";

  // Normalize text: remove extra spaces and clean up
  const cleanText = rawText
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .replace(/\t/g, "  ")
    .trim();

  // Split into paragraphs
  const paragraphs = cleanText.split(/\n\s*\n/).filter((p) => p.trim());

  let html = "";
  let inList = false;
  let listType = "ul"; // ul hoặc ol

  paragraphs.forEach((para) => {
    const lines = para
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line);

    lines.forEach((line, index) => {
      // Detect different types of content
      const lineType = detectLineType(line);

      switch (lineType.type) {
        case "title":
          if (inList) {
            html += `</${listType}>`;
            inList = false;
          }
          html += `<h4 class="job-section-title">${lineType.content}</h4>`;
          break;

        case "subtitle":
          if (inList) {
            html += `</${listType}>`;
            inList = false;
          }
          html += `<h5 class="job-subsection">${lineType.content}</h5>`;
          break;

        case "list-item":
          if (!inList || listType !== lineType.listType) {
            if (inList) html += `</${listType}>`;
            listType = lineType.listType;
            html += `<${listType} class="job-list">`;
            inList = true;
          }
          html += `<li>${lineType.content}</li>`;
          break;

        case "paragraph":
          if (inList) {
            html += `</${listType}>`;
            inList = false;
          }
          html += `<p class="job-paragraph">${lineType.content}</p>`;
          break;

        case "contact":
          if (inList) {
            html += `</${listType}>`;
            inList = false;
          }
          html += `<div class="contact-info">${lineType.content}</div>`;
          break;
      }
    });
  });

  // Close any remaining list
  if (inList) {
    html += `</${listType}>`;
  }

  return html || "<p>Không có mô tả chi tiết.</p>";
}

// Comprehensive line type detection
function detectLineType(line) {
  const trimmed = line.trim();

  // Title patterns (section headers)
  if (isSectionTitle(trimmed)) {
    return {
      type: "title",
      content: cleanTitle(trimmed),
    };
  }

  // Subtitle patterns
  if (isSubtitle(trimmed)) {
    return {
      type: "subtitle",
      content: cleanSubtitle(trimmed),
    };
  }

  // List item patterns
  const listMatch = matchListItem(trimmed);
  if (listMatch) {
    return {
      type: "list-item",
      content: highlightKeywords(listMatch.content),
      listType: listMatch.listType,
    };
  }

  // Contact information
  if (isContactInfo(trimmed)) {
    return {
      type: "contact",
      content: formatContactInfo(trimmed),
    };
  }

  // Regular paragraph
  return {
    type: "paragraph",
    content: highlightKeywords(trimmed),
  };
}

// Section title detection
function isSectionTitle(text) {
  const titlePatterns = [
    /^(MÔ TẢ CÔNG VIỆC|JOB DESCRIPTION|TRÁCH NHIỆM|RESPONSIBILITIES?):/i,
    /^(YÊU CẦU|REQUIREMENTS?|QUALIFICATIONS?):/i,
    /^(QUYỀN LỢI|BENEFITS?|PHÚC LỢI):/i,
    /^(KINH NGHIỆM|EXPERIENCE):/i,
    /^(KỸ NĂNG|SKILLS?):/i,
    /^(THÔNG TIN|INFORMATION|CONTACT):/i,
    /^[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ\s]{10,}$/,
    /^[IVX]+\.\s/,
    /^\d+\.\s*[A-ZÀÁẠẢÃ]/,
  ];

  return (
    titlePatterns.some((pattern) => pattern.test(text)) ||
    (text.endsWith(":") && text.length > 5 && text.length < 50) ||
    (text === text.toUpperCase() && text.length > 5 && text.length < 50)
  );
}

// Subtitle detection
function isSubtitle(text) {
  return /^[a-zA-Z0-9À-ỹ\s]{5,30}:$/.test(text) && !isSectionTitle(text);
}

// List item matching
function matchListItem(text) {
  const patterns = [
    { regex: /^[•●▪▫-]\s*(.+)/, listType: "ul" },
    { regex: /^[\*]\s*(.+)/, listType: "ul" },
    { regex: /^[+]\s*(.+)/, listType: "ul" },
    { regex: /^\d+[\.\)]\s*(.+)/, listType: "ol" },
    { regex: /^[a-zA-Z][\.\)]\s*(.+)/, listType: "ol" },
    { regex: /^[IVX]+[\.\)]\s*(.+)/, listType: "ol" },
    // Vietnamese patterns
    { regex: /^-\s*(.+)/, listType: "ul" },
    { regex: /^Có\s+(.+)/, listType: "ul" },
    { regex: /^Biết\s+(.+)/, listType: "ul" },
    { regex: /^Thành thạo\s+(.+)/, listType: "ul" },
  ];

  for (const pattern of patterns) {
    const match = text.match(pattern.regex);
    if (match) {
      return {
        content: match[1].trim(),
        listType: pattern.listType,
      };
    }
  }

  return null;
}

// Contact info detection
function isContactInfo(text) {
  return (
    /\b(email|phone|tel|address|liên hệ|điện thoại|địa chỉ):/i.test(text) ||
    /\b[\w.-]+@[\w.-]+\.\w+\b/.test(text) ||
    /\b(\+84|0)\d{9,10}\b/.test(text)
  );
}

// Clean and format functions
function cleanTitle(text) {
  return text
    .replace(/^[:\-\s]+|[:\-\s]+$/g, "")
    .replace(/^(I+V*X*|\d+)[\.\)]\s*/, "")
    .trim();
}

function cleanSubtitle(text) {
  return text.replace(/:$/, "").trim();
}

function formatContactInfo(text) {
  return text
    .replace(/\b([\w.-]+@[\w.-]+\.\w+)\b/g, '<a href="mailto:$1">$1</a>')
    .replace(/\b((\+84|0)\d{9,10})\b/g, '<a href="tel:$1">$1</a>');
}

// Enhanced keyword highlighting
function highlightKeywords(text) {
  const keywordGroups = {
    tech: [
      "JavaScript",
      "TypeScript",
      "Python",
      "Java",
      "C#",
      "PHP",
      "Ruby",
      "Go",
      "Rust",
      "React",
      "Vue",
      "Angular",
      "Node.js",
      "Express",
      "Django",
      "Laravel",
      "Rails",
      "HTML",
      "CSS",
      "SCSS",
      "Tailwind",
      "Bootstrap",
      "MySQL",
      "PostgreSQL",
      "MongoDB",
      "Redis",
      "SQLite",
      "Docker",
      "Kubernetes",
      "AWS",
      "Azure",
      "GCP",
      "Git",
      "GitHub",
      "GitLab",
      "API",
      "REST",
      "GraphQL",
      "JSON",
      "XML",
    ],
    business: [
      "Full-time",
      "Part-time",
      "Remote",
      "Hybrid",
      "Freelance",
      "Junior",
      "Senior",
      "Lead",
      "Manager",
      "Director",
      "Agile",
      "Scrum",
      "Kanban",
      "DevOps",
      "CI/CD",
    ],
    vietnamese: [
      "Lập trình",
      "Phát triển",
      "Thiết kế",
      "Quản lý",
      "Kinh nghiệm",
      "Tốt nghiệp",
      "Đại học",
      "Cao đẳng",
      "Chứng chỉ",
    ],
  };

  let result = text;

  Object.entries(keywordGroups).forEach(([group, keywords]) => {
    keywords.forEach((keyword) => {
      const regex = new RegExp(`\\b${escapeRegex(keyword)}\\b`, "gi");
      result = result.replace(
        regex,
        `<span class="keyword keyword-${group}">${keyword}</span>`
      );
    });
  });

  // Highlight salary/money
  result = result.replace(
    /\b(\d{1,3}(?:[,.]?\d{3})*)\s*(VNĐ|USD|triệu|tr|k|nghìn)\b/gi,
    '<span class="salary-highlight">$1 $2</span>'
  );

  // Highlight years of experience
  result = result.replace(
    /\b(\d+)\s*(năm|year[s]?)\s*(kinh nghiệm|experience)\b/gi,
    '<span class="experience-highlight">$1 $2 $3</span>'
  );

  return result;
}

function escapeRegex(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Main job loading function - no API calls needed
async function loadJobDetail() {
  try {
    // Show loading state
    jobDetailEl.innerHTML = `
      <div class="loading">
        <div class="loading-spinner"></div>
        <p>Đang tải chi tiết công việc...</p>
      </div>
    `;

    const response = await fetch(`http://127.0.0.1:8000/api/jobs/${jobId}/`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const job = await response.json();

    // Process job data
    const title = job.title || "Không có tiêu đề";
    const company = job.company || "Không rõ công ty";
    const salary = processSalary(job.salary);
    const description = formatJobDescription(job.description || "");

    const locationsHtml = (job.location || [])
      .filter((loc) => loc?.trim())
      .map((loc) => `<span class="location-tag">${loc}</span>`)
      .join("");

    const tagsHtml = (job.tags || [])
      .filter((tag) => tag?.trim())
      .map((tag) => `<span class="skill-tag">${tag}</span>`)
      .join("");

    // Additional job metadata
    const postedDate = job.posted_date
      ? formatDate(job.posted_date)
      : "Không rõ";
    const deadline = job.deadline ? formatDate(job.deadline) : "Không rõ";
    const jobType = job.job_type || "Full-time";

    jobDetailEl.innerHTML = `
      <div class="job-container">
        <div class="job-header">
          <div class="job-title-section">
            <h1 class="job-title">${title}</h1>
            <h2 class="company-name">${company}</h2>
          </div>
          
          <div class="job-meta">
            <div class="meta-row">
              <span class="meta-item salary">💰 ${salary}</span>
              <span class="meta-item job-type">⏰ ${jobType}</span>
            </div>
            <div class="meta-row">
              <span class="meta-item posted">📅 Đăng: ${postedDate}</span>
              <span class="meta-item deadline">⏳ Hạn: ${deadline}</span>
            </div>
          </div>
          
          ${
            locationsHtml ? `<div class="locations">${locationsHtml}</div>` : ""
          }
          ${tagsHtml ? `<div class="skills">${tagsHtml}</div>` : ""}
        </div>

        <div class="job-content">
          <div class="job-description">
            ${description}
          </div>
        </div>

        <div class="job-actions">
          <button class="btn btn-primary apply-btn" onclick="applyJob(${
            job.id
          })">
            <span class="btn-icon">📝</span>
            Ứng tuyển ngay
          </button>
          <button class="btn btn-secondary save-btn" onclick="saveJob(${
            job.id
          })">
            <span class="btn-icon">❤️</span>
            Lưu tin
          </button>
          <button class="btn btn-secondary share-btn" onclick="shareJob(${
            job.id
          })">
            <span class="btn-icon">📤</span>
            Chia sẻ
          </button>
        </div>
      </div>
    `;

    // Add some CSS for better styling
    addJobDetailStyles();
  } catch (err) {
    console.error("Lỗi khi lấy job:", err);
    jobDetailEl.innerHTML = `
      <div class="error-container">
        <div class="error-icon">❌</div>
        <h3>Không thể tải chi tiết công việc</h3>
        <p class="error-message">${err.message}</p>
        <div class="error-actions">
          <button class="btn btn-primary" onclick="loadJobDetail()">🔄 Thử lại</button>
          <button class="btn btn-secondary" onclick="history.back()">⬅️ Quay lại</button>
        </div>
      </div>
    `;
  }
}

// Helper functions
function processSalary(salary) {
  if (!salary || salary === "Sign in to view salary") {
    return `${Math.floor(Math.random() * (30 - 8 + 1)) + 8} - ${
      Math.floor(Math.random() * (50 - 15 + 1)) + 15
    } triệu VNĐ`;
  }
  return salary;
}

function formatDate(dateString) {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN");
  } catch {
    return dateString;
  }
}

function addJobDetailStyles() {
  if (document.getElementById("job-detail-styles")) return;

  const styles = `
    <style id="job-detail-styles">
      .job-container { max-width: 800px; margin: 0 auto; padding: 20px; }
      .job-header { background: #f8f9fa; padding: 24px; border-radius: 12px; margin-bottom: 24px; }
      .job-title { font-size: 2em; margin: 0 0 8px 0; color: #2c3e50; }
      .company-name { font-size: 1.3em; margin: 0 0 16px 0; color: #3498db; }
      .job-meta { margin: 16px 0; }
      .meta-row { display: flex; gap: 24px; margin-bottom: 8px; }
      .meta-item { font-size: 0.95em; color: #666; }
      .locations, .skills { margin: 16px 0; }
      .location-tag, .skill-tag { 
        display: inline-block; padding: 4px 12px; margin: 4px 4px 4px 0;
        background: #e3f2fd; color: #1976d2; border-radius: 16px; font-size: 0.9em;
      }
      .skill-tag { background: #f3e5f5; color: #7b1fa2; }
      .job-content { background: white; padding: 24px; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
      .job-section-title { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px; margin: 24px 0 16px 0; }
      .job-subsection { color: #34495e; margin: 16px 0 8px 0; }
      .job-list { margin: 16px 0; padding-left: 20px; }
      .job-list li { margin-bottom: 8px; line-height: 1.6; }
      .job-paragraph { line-height: 1.7; margin-bottom: 16px; }
      .keyword { font-weight: 600; padding: 2px 4px; border-radius: 4px; }
      .keyword-tech { background: #e8f5e8; color: #2e7d32; }
      .keyword-business { background: #fff3e0; color: #f57c00; }
      .salary-highlight { background: #e8f5e8; color: #2e7d32; font-weight: 600; }
      .experience-highlight { background: #e3f2fd; color: #1976d2; font-weight: 600; }
      .contact-info { background: #f5f5f5; padding: 12px; border-radius: 8px; margin: 12px 0; }
      .job-actions { display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }
      .btn { padding: 12px 24px; border: none; border-radius: 8px; cursor: pointer; font-size: 1em; display: flex; align-items: center; gap: 8px; transition: all 0.3s; }
      .btn-primary { background: #3498db; color: white; }
      .btn-primary:hover { background: #2980b9; transform: translateY(-2px); }
      .btn-secondary { background: #ecf0f1; color: #2c3e50; }
      .btn-secondary:hover { background: #d5dbdb; }
      .loading { text-align: center; padding: 40px; }
      .loading-spinner { width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; margin: 0 auto 16px; }
      @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      .error-container { text-align: center; padding: 40px; }
      .error-icon { font-size: 3em; margin-bottom: 16px; }
      .error-actions { margin-top: 24px; display: flex; gap: 12px; justify-content: center; }
    </style>
  `;
  document.head.insertAdjacentHTML("beforeend", styles);
}

// Initialize
loadJobDetail();

// Enhanced job action functions
window.applyJob = function (jobId) {
  console.log("Applying for job:", jobId);
  // Show application modal or redirect
  showApplicationModal(jobId);
};

window.saveJob = function (jobId) {
  console.log("Saving job:", jobId);
  const savedJobs = JSON.parse(localStorage.getItem("savedJobs") || "[]");
  if (!savedJobs.includes(jobId)) {
    savedJobs.push(jobId);
    localStorage.setItem("savedJobs", JSON.stringify(savedJobs));
    showNotification("✅ Đã lưu tin tuyển dụng!", "success");
  } else {
    showNotification("ℹ️ Tin này đã được lưu trước đó!", "info");
  }
};

window.shareJob = function (jobId) {
  const url = window.location.href;
  const title =
    document.querySelector(".job-title")?.textContent ||
    "Việc làm từ JobPortal";

  if (navigator.share) {
    navigator.share({ title, url });
  } else {
    navigator.clipboard.writeText(url).then(() => {
      showNotification("📋 Đã copy link chia sẻ!", "success");
    });
  }
};

// Utility functions
function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 1000;
    padding: 12px 20px; border-radius: 8px; color: white;
    background: ${
      type === "success" ? "#27ae60" : type === "error" ? "#e74c3c" : "#3498db"
    };
    box-shadow: 0 4px 12px rgba(0,0,0,0.2); animation: slideIn 0.3s ease;
  `;

  document.body.appendChild(notification);
  setTimeout(() => notification.remove(), 3000);
}

function showApplicationModal(jobId) {
  const modal = document.createElement("div");
  modal.innerHTML = `
    <div class="modal-overlay" onclick="this.parentElement.remove()">
      <div class="modal-content" onclick="event.stopPropagation()">
        <h3>Ứng tuyển công việc</h3>
        <p>Bạn có muốn ứng tuyển vào vị trí này không?</p>
        <div class="modal-actions">
          <button class="btn btn-primary" onclick="proceedToApply(${jobId}); this.closest('.modal-overlay').parentElement.remove();">Tiếp tục</button>
          <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').parentElement.remove();">Hủy</button>
        </div>
      </div>
    </div>
  `;
  modal.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 2000;
  `;

  const styles = `
    .modal-overlay { background: rgba(0,0,0,0.5); width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
    .modal-content { background: white; padding: 24px; border-radius: 12px; max-width: 400px; text-align: center; }
    .modal-actions { margin-top: 20px; display: flex; gap: 12px; justify-content: center; }
  `;

  if (!document.getElementById("modal-styles")) {
    document.head.insertAdjacentHTML(
      "beforeend",
      `<style id="modal-styles">${styles}</style>`
    );
  }

  document.body.appendChild(modal);
}

window.proceedToApply = function (jobId) {
  showNotification("🚀 Đang chuyển đến trang ứng tuyển...", "success");
  // TODO: Redirect to application page
  setTimeout(() => {
    window.location.href = `/apply?jobId=${jobId}`;
  }, 1000);
};
