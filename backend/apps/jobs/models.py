from django.db import models


class JobListing(models.Model):
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.TextField()
    salary = models.CharField(max_length=100, blank=True,
                              null=True)  # Chuẩn bị cho các dạng salary text như "Sign In to view salary"
    posted_at = models.CharField(max_length=100, blank=True, null=True)  # Lưu nguyên text mô tả đăng tuyển
    experience = models.CharField(max_length=50, blank=True, null=True)
    level = models.CharField(max_length=50, blank=True, null=True)
    tags = models.JSONField(default=list)  # Lưu mảng tags/kỹ năng
    url = models.URLField(max_length=500)
    source = models.URLField(max_length=500)
    description = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.company}"

    @classmethod
    def create_from_json(cls, job_json):
        return cls.objects.create(
            title=job_json.get("title", ""),
            company=job_json.get("company", ""),
            location=job_json.get("location", ""),
            salary=job_json.get("salary", ""),
            posted_at=job_json.get("posted_at", ""),
            experience=job_json.get("experience", ""),
            level=job_json.get("level", ""),
            tags=job_json.get("tags", []),
            url=job_json.get("url", ""),
            source=job_json.get("source", ""),
            description=job_json.get("description", ""),
        )
