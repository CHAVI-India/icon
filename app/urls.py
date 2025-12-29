from django.urls import path
from app import views

urlpatterns = [
    path('', views.dicom_index, name='dicom_index'),
    path('upload/', views.upload_dicom_file, name='upload_dicom_file'),
    path('process/<int:dicom_file_id>/', views.process_dicom_file_view, name='admin:process_dicom_file'),
    path('processing/progress/', views.dicom_processing_progress, name='dicom_processing_progress'),
    path('api/task-status/<str:task_id>/', views.task_status, name='task_status'),
    path('manage-files/', views.manage_files, name='manage_files'),
    path('patients/', views.view_patients, name='view_patients'),
    path('patients/<int:patient_id>/', views.view_patient_detail, name='view_patient_detail'),
    path('studies/', views.view_studies, name='view_studies'),
    path('studies/<int:study_id>/', views.view_study_detail, name='view_study_detail'),
    path('templates/', views.view_templates, name='view_templates'),
    path('rulegroups/', views.view_rulegroups, name='view_rulegroups'),
    path('rulegroups/<int:rulegroup_id>/', views.view_rulegroup_detail, name='view_rulegroup_detail'),
]
