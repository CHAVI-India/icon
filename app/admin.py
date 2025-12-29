from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.contrib import messages

from app.models import (
    DICOMFile, RuleGroup, Ruleset, Rule, PrescriptionTemplate, 
    Prescription, Patient, DICOMStudy, DICOMSeries, DICOMInstance,
    ImageInformation, RTStructureSetInformation, RTStructureROI
)
from app.tasks import process_dicom_file_task


@admin.register(DICOMFile)
class DICOMFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'file', 'uploaded_by', 'processing_status', 'created_at', 'processing_actions']
    list_filter = ['processing_status', 'created_at']
    search_fields = ['file', 'uploaded_by__username']
    readonly_fields = ['processing_status', 'date_processing_completed', 'processing_log_data', 'created_at', 'updated_at']
    actions = ['process_selected_files']
    
    def processing_actions(self, obj):
        """Display action buttons for processing"""
        if obj.processing_status == 'pending':
            process_url = reverse('admin:process_dicom_file', args=[obj.id])
            return format_html(
                '<a class="button" href="{}">Process Now</a>',
                process_url
            )
        elif obj.processing_status == 'in_progress':
            return format_html('<span style="color: orange;">Processing...</span>')
        elif obj.processing_status == 'completed':
            return format_html('<span style="color: green;">✓ Completed</span>')
        elif obj.processing_status == 'failed':
            return format_html('<span style="color: red;">✗ Failed</span>')
        return '-'
    
    processing_actions.short_description = 'Actions'
    
    def process_selected_files(self, request, queryset):
        """Admin action to process selected DICOM files"""
        # Filter only pending files
        pending_files = queryset.filter(processing_status='pending')
        
        if not pending_files.exists():
            self.message_user(request, "No pending files selected.", messages.WARNING)
            return
        
        # Start processing tasks
        task_ids = []
        for dicom_file in pending_files:
            task = process_dicom_file_task.delay(dicom_file.id)
            task_ids.append(task.id)
        
        # Redirect to progress page with task IDs
        task_ids_str = ','.join(task_ids)
        return redirect(f"{reverse('dicom_processing_progress')}?task_ids={task_ids_str}")
    
    process_selected_files.short_description = "Process selected DICOM files"


@admin.register(RuleGroup)
class RuleGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'rulegroup_name', 'rulegroup_description', 'created_at']
    search_fields = ['rulegroup_name', 'rulegroup_description']


@admin.register(Ruleset)
class RulesetAdmin(admin.ModelAdmin):
    list_display = ['id', 'ruleset_name', 'rulegroup', 'ruleset_order', 'ruleset_combination', 'created_at']
    list_filter = ['rulegroup']
    search_fields = ['ruleset_name']
    ordering = ['rulegroup', 'ruleset_order']


@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ['id', 'ruleset', 'rule_order', 'parameter_to_be_matched', 'matching_operator', 'matching_value']
    list_filter = ['ruleset__rulegroup', 'parameter_to_be_matched', 'matching_operator']
    search_fields = ['matching_value']
    ordering = ['ruleset', 'rule_order']


@admin.register(PrescriptionTemplate)
class PrescriptionTemplateAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'cancer_site', 'cancer_side', 'treatment_modality', 'rulegroup_name']
    list_filter = ['cancer_side', 'treatment_modality']
    search_fields = ['name', 'cancer_site']


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'prescription_template', 'roi_name', 'dose_prescribed', 'dose_unit', 'fractions_prescribed']
    list_filter = ['prescription_template', 'dose_unit']
    search_fields = ['roi_name']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['id', 'unique_patient_id', 'patient_name', 'patient_dob', 'patient_sex', 'created_at']
    search_fields = ['unique_patient_id', 'patient_name']
    list_filter = ['patient_sex']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DICOMStudy)
class DICOMStudyAdmin(admin.ModelAdmin):
    list_display = ['id', 'study_instance_uid', 'patient', 'study_description', 'study_date', 'created_at']
    search_fields = ['study_instance_uid', 'study_description']
    list_filter = ['study_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DICOMSeries)
class DICOMSeriesAdmin(admin.ModelAdmin):
    list_display = ['id', 'series_instance_uid', 'dicom_study', 'series_description', 'series_date', 'created_at']
    search_fields = ['series_instance_uid', 'series_description']
    list_filter = ['series_date']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(DICOMInstance)
class DICOMInstanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'sop_instance_uid', 'dicom_series', 'modality', 'created_at']
    search_fields = ['sop_instance_uid']
    list_filter = ['modality']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ImageInformation)
class ImageInformationAdmin(admin.ModelAdmin):
    list_display = ['id', 'dicom_instance', 'slice_location', 'slice_thickness', 'instance_number']
    search_fields = ['dicom_instance__sop_instance_uid']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RTStructureSetInformation)
class RTStructureSetInformationAdmin(admin.ModelAdmin):
    list_display = ['id', 'dicom_instance', 'number_of_roi', 'prescription_template_id', 'created_at']
    search_fields = ['dicom_instance__sop_instance_uid']
    list_filter = ['prescription_template_id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(RTStructureROI)
class RTStructureROIAdmin(admin.ModelAdmin):
    list_display = ['id', 'rt_structure_set', 'roi_number', 'roi_name', 'created_at']
    search_fields = ['roi_name']
    list_filter = ['rt_structure_set']
    readonly_fields = ['created_at', 'updated_at']
