from django_filters import rest_framework as filters
from .models import JobListing

class JobListingFilter(filters.FilterSet):
    location = filters.CharFilter(method='filter_location')
    tags = filters.CharFilter(method='filter_tags')

    def filter_location(self, queryset, name, value):
        return queryset.filter(location__icontains=value)

    def filter_tags(self, queryset, name, value):
        return queryset.filter(tags__icontains=value)

    class Meta:
        model = JobListing
        fields = ['location']
