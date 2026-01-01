from django.urls import path
from trainer import views

app_name = 'trainer'

urlpatterns = [
    path('', views.upload_training_data, name='upload_training_data'),
    path('training-data/', views.training_data_list, name='training_data_list'),
    path('training-data/<int:archive_id>/', views.archive_detail, name='archive_detail'),
    path('training-data/<int:archive_id>/process/', views.process_training_archive, name='process_training_archive'),
    path('image-series/<int:series_id>/', views.image_series_detail, name='image_series_detail'),
    path('rtstruct/<int:rtstruct_id>/', views.rtstruct_detail, name='rtstruct_detail'),
    path('task-progress/<str:task_id>/', views.task_progress, name='task_progress'),
]
