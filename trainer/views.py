from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from celery.result import AsyncResult
from trainer.models import (
    TrainingDataSetArchive,
    TrainingImage,
    TrainingRTStructureSetFile,
    TrainingRTStructureSetROI,
    TrainingRTPlanAndDoseFile
)
from trainer.tasks import process_training_data_archive_task


@login_required
def upload_training_data(request):
    if request.method == 'POST':
        if 'training_data_file' not in request.FILES:
            messages.error(request, 'No file was uploaded.')
            return redirect('trainer:upload_training_data')
        
        uploaded_file = request.FILES['training_data_file']
        
        if not uploaded_file.name.endswith('.zip'):
            messages.error(request, 'Only ZIP files are allowed.')
            return redirect('trainer:upload_training_data')
        
        try:
            archive = TrainingDataSetArchive.objects.create(
                file=uploaded_file,
                uploaded_by=request.user
            )
            messages.success(request, f'File "{uploaded_file.name}" uploaded successfully!')
            return redirect('trainer:training_data_list')
        except Exception as e:
            messages.error(request, f'Error uploading file: {str(e)}')
            return redirect('trainer:upload_training_data')
    
    return render(request, 'trainer/upload_training_data.html')


@login_required
@require_http_methods(["GET"])
def training_data_list(request):
    archives = TrainingDataSetArchive.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'trainer/training_data_list.html', {
        'archives': archives
    })


@login_required
@require_http_methods(["POST"])
def process_training_archive(request, archive_id):
    archive = get_object_or_404(TrainingDataSetArchive, id=archive_id, uploaded_by=request.user)
    
    task = process_training_data_archive_task.delay(archive_id)
    
    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'message': 'Processing started'
    })


@login_required
@require_http_methods(["GET"])
def task_progress(request, task_id):
    result = AsyncResult(task_id)
    
    if result.state == 'PENDING':
        response = {
            'state': result.state,
            'current': 0,
            'total': 100,
            'status': 'Pending...'
        }
    elif result.state == 'PROGRESS':
        response = {
            'state': result.state,
            'current': result.info.get('current', 0),
            'total': result.info.get('total', 100),
            'status': result.info.get('description', '')
        }
    elif result.state == 'SUCCESS':
        response = {
            'state': result.state,
            'current': 100,
            'total': 100,
            'status': 'Complete!',
            'result': result.info
        }
    else:
        response = {
            'state': result.state,
            'current': 0,
            'total': 100,
            'status': str(result.info)
        }
    
    return JsonResponse(response)


@login_required
def archive_detail(request, archive_id):
    archive = get_object_or_404(TrainingDataSetArchive, id=archive_id, uploaded_by=request.user)
    
    images = TrainingImage.objects.filter(training_data_set_archive=archive).order_by('patient_id', 'series_description')
    
    context = {
        'archive': archive,
        'images': images,
        'total_images': images.count(),
    }
    
    return render(request, 'trainer/archive_detail.html', context)


@login_required
def image_series_detail(request, series_id):
    image_series = get_object_or_404(TrainingImage, id=series_id, training_data_set_archive__uploaded_by=request.user)
    
    rtstructs = TrainingRTStructureSetFile.objects.filter(referenced_series_instance_uid=image_series)
    
    context = {
        'image_series': image_series,
        'rtstructs': rtstructs,
    }
    
    return render(request, 'trainer/image_series_detail.html', context)


@login_required
def rtstruct_detail(request, rtstruct_id):
    rtstruct = get_object_or_404(
        TrainingRTStructureSetFile, 
        id=rtstruct_id,
        referenced_series_instance_uid__training_data_set_archive__uploaded_by=request.user
    )
    
    rois = TrainingRTStructureSetROI.objects.filter(training_rt_structure_set=rtstruct)
    plans_doses = TrainingRTPlanAndDoseFile.objects.filter(structureset_referenced_series_intance_uid=rtstruct)
    
    context = {
        'rtstruct': rtstruct,
        'rois': rois,
        'plans_doses': plans_doses,
    }
    
    return render(request, 'trainer/rtstruct_detail.html', context)
