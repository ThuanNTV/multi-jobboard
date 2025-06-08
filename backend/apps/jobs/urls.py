from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import JobListingViewSet

router = DefaultRouter()
router.register(r'jobs', JobListingViewSet, basename='joblisting')

urlpatterns = [
    path('api/', include(router.urls)),
]
