from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from celery.result import AsyncResult
import json

from app.models import (
    DICOMFile, Patient, DICOMStudy, DICOMSeries, DICOMInstance,
    PrescriptionTemplate, RuleGroup, Ruleset, Rule
)
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
        'task_ids_json': json.dumps(task_ids),
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


@staff_member_required
def manage_files(request):
    """
    Frontend view to manage DICOM files.
    """
    dicom_files = DICOMFile.objects.all().order_by('-created_at')
    
    context = {
        'dicom_files': dicom_files,
    }
    
    return render(request, 'app/manage_files.html', context)


@staff_member_required
def view_patients(request):
    """
    Frontend view to display all patients.
    """
    patients = Patient.objects.all().order_by('patient_name')
    
    context = {
        'patients': patients,
    }
    
    return render(request, 'app/view_patients.html', context)


@staff_member_required
def view_studies(request):
    """
    Frontend view to display all DICOM studies.
    """
    studies = DICOMStudy.objects.all().select_related('patient').order_by('-study_date')
    
    context = {
        'studies': studies,
    }
    
    return render(request, 'app/view_studies.html', context)


@staff_member_required
def view_templates(request):
    """
    Frontend view to display all prescription templates.
    """
    templates = PrescriptionTemplate.objects.all().select_related('rulegroup_name').order_by('name')
    
    context = {
        'templates': templates,
    }
    
    return render(request, 'app/view_templates.html', context)


@staff_member_required
def view_rulegroups(request):
    """
    Frontend view to display all rule groups.
    """
    rulegroups = RuleGroup.objects.all().order_by('rulegroup_name')
    
    context = {
        'rulegroups': rulegroups,
    }
    
    return render(request, 'app/view_rulegroups.html', context)


@staff_member_required
def view_rulegroup_detail(request, rulegroup_id):
    """
    Frontend view to display details of a specific rule group including its rulesets and rules.
    """
    rulegroup = get_object_or_404(RuleGroup, id=rulegroup_id)
    rulesets = Ruleset.objects.filter(rulegroup=rulegroup).order_by('ruleset_order')
    
    rulesets_with_rules = []
    for ruleset in rulesets:
        rules = Rule.objects.filter(ruleset=ruleset).order_by('rule_order')
        rulesets_with_rules.append({
            'ruleset': ruleset,
            'rules': rules
        })
    
    context = {
        'rulegroup': rulegroup,
        'rulesets_with_rules': rulesets_with_rules,
    }
    
    return render(request, 'app/rulegroup_detail.html', context)


@staff_member_required
def view_patient_detail(request, patient_id):
    """
    Frontend view to display detailed information about a patient including all studies, series, and instances.
    """
    patient = get_object_or_404(Patient, id=patient_id)
    studies = DICOMStudy.objects.filter(patient=patient).order_by('-study_date')
    
    studies_with_details = []
    for study in studies:
        series_list = DICOMSeries.objects.filter(dicom_study=study).order_by('series_instance_uid')
        series_with_instances = []
        
        for series in series_list:
            instances = DICOMInstance.objects.filter(dicom_series=series).order_by('sop_instance_uid')
            series_with_instances.append({
                'series': series,
                'instances': instances,
                'instance_count': instances.count()
            })
        
        studies_with_details.append({
            'study': study,
            'series_list': series_with_instances,
            'series_count': series_list.count(),
            'total_instances': sum(item['instance_count'] for item in series_with_instances)
        })
    
    context = {
        'patient': patient,
        'studies_with_details': studies_with_details,
        'total_studies': studies.count(),
    }
    
    return render(request, 'app/patient_detail.html', context)


@staff_member_required
def view_study_detail(request, study_id):
    """
    Frontend view to display detailed information about a study including all series and instances.
    """
    study = get_object_or_404(DICOMStudy, id=study_id)
    series_list = DICOMSeries.objects.filter(dicom_study=study).order_by('series_instance_uid')
    
    series_with_instances = []
    for series in series_list:
        instances = DICOMInstance.objects.filter(dicom_series=series).order_by('sop_instance_uid')
        series_with_instances.append({
            'series': series,
            'instances': instances,
            'instance_count': instances.count()
        })
    
    context = {
        'study': study,
        'series_with_instances': series_with_instances,
        'total_series': series_list.count(),
        'total_instances': sum(item['instance_count'] for item in series_with_instances)
    }
    
    return render(request, 'app/study_detail.html', context)
