from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from celery.result import AsyncResult

from app.models import DICOMFile
from app.tasks import process_dicom_file_task


@staff_member_required
def dicom_index(request):
    """
    Frontend landing page showing DICOM files and processing status.
    """
    dicom_files = DICOMFile.objects.all().order_by('-created_at')
    
    context = {
        'dicom_files': dicom_files,
        'pending_count': dicom_files.filter(processing_status='pending').count(),
        'processing_count': dicom_files.filter(processing_status='in_progress').count(),
        'completed_count': dicom_files.filter(processing_status='completed').count(),
        'failed_count': dicom_files.filter(processing_status='failed').count(),
    }
    
    return render(request, 'app/index.html', context)


@staff_member_required
def upload_dicom_file(request):
    """
    Handle DICOM file upload from frontend.
    """
    if request.method == 'POST':
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            
            # Create DICOMFile instance
            dicom_file = DICOMFile(
                file=uploaded_file,
                uploaded_by=request.user
            )
            dicom_file.save()
            
            messages.success(request, f'File "{uploaded_file.name}" uploaded successfully!')
            
            # Check if user wants to process immediately
            if request.POST.get('process_now') == 'true':
                task = process_dicom_file_task.delay(dicom_file.id)
                return redirect(f"{reverse('dicom_processing_progress')}?task_ids={task.id}")
            
            return redirect('dicom_index')
        else:
            messages.error(request, 'No file was uploaded.')
            return redirect('dicom_index')
    
    return render(request, 'app/upload.html')


@staff_member_required
def process_dicom_file_view(request, dicom_file_id):
    """
    View to start processing a single DICOM file and redirect to progress page.
    """
    dicom_file = get_object_or_404(DICOMFile, id=dicom_file_id)
    
    # Start the processing task
    task = process_dicom_file_task.delay(dicom_file_id)
    
    # Redirect to progress page with task ID
    return redirect(f"{reverse('dicom_processing_progress')}?task_ids={task.id}")


@staff_member_required
def dicom_processing_progress(request):
    """
    View to display processing progress for one or more tasks.
    """
    task_ids_str = request.GET.get('task_ids', '')
    task_ids = [tid.strip() for tid in task_ids_str.split(',') if tid.strip()]
    
    if not task_ids:
        return render(request, 'app/processing_error.html', {
            'error': 'No task IDs provided'
        })
    
    context = {
        'task_ids': task_ids,
        'task_ids_json': task_ids_str,
    }
    
    return render(request, 'app/processing_progress.html', context)


@staff_member_required
def task_status(request, task_id):
    """
    API endpoint to get the status of a Celery task.
    Returns JSON with task state and progress information.
    """
    result = AsyncResult(task_id)
    
    response_data = {
        'task_id': task_id,
        'state': result.state,
        'ready': result.ready(),
    }
    
    if result.state == 'PENDING':
        response_data.update({
            'current': 0,
            'total': 100,
            'percent': 0,
            'description': 'Waiting to start...'
        })
    elif result.state == 'PROGRESS':
        info = result.info
        response_data.update({
            'current': info.get('current', 0),
            'total': info.get('total', 100),
            'percent': info.get('percent', 0),
            'description': info.get('description', 'Processing...')
        })
    elif result.state == 'SUCCESS':
        response_data.update({
            'current': 100,
            'total': 100,
            'percent': 100,
            'description': 'Completed!',
            'result': result.result
        })
    elif result.state == 'FAILURE':
        response_data.update({
            'current': 100,
            'total': 100,
            'percent': 100,
            'description': f'Error: {str(result.info)}',
            'error': str(result.info)
        })
    else:
        response_data.update({
            'description': result.state
        })
    
    return JsonResponse(response_data)
