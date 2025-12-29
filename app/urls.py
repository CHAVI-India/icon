from django.urls import path
from app import views

urlpatterns = [
    path('', views.dicom_index, name='dicom_index'),
    path('upload/', views.upload_dicom_file, name='upload_dicom_file'),
    path('process/<int:dicom_file_id>/', views.process_dicom_file_view, name='admin:process_dicom_file'),
    path('processing/progress/', views.dicom_processing_progress, name='dicom_processing_progress'),
    path('api/task-status/<str:task_id>/', views.task_status, name='task_status'),
]
