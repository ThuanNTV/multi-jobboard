from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from .models import JobListing
from .serializers import JobListingSerializer

class JobListingViewSet(viewsets.ModelViewSet):
    queryset = JobListing.objects.all().order_by('-posted_at')
    serializer_class = JobListingSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['location', 'source']
    search_fields = ['title', 'company', 'skills']
    ordering_fields = ['posted_date', 'salary_min']

    # Bạn có thể override get_queryset() để filter salary range, skills nâng cao
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticatedOrReadOnly]
        return [permission() for permission in permission_classes]
