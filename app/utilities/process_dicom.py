# This function will run as a celery task to extract metadata to extract from DICOM files and store it in the database.
# This function will take as input the individual DICOM file, extract information from it and store it properly. 
# It will use pydicom for the processing. Use force = True and check if the modality tag is present to process. If Modality tag is not present then skip the processing. 
# It can handle either a single file path or a list of file paths provided by another function running before it. 
# If multiple file paths are provided it will process each file sequentially
# Information extracted will be stored in the Patient, DICOMStudy, DICOMSeries, DICOMInstance, ImageInformation, RTStructureSetInformation and RTStructureROI models. 
# The Patient, DICOMStudy, DICOMSeries, DICOMInstance data will be saved for each file ensuring that if the data already existing it will be updated assuming something has changed. If the file has a dicom modality like CT / MR / PET then the ImageInformation is to be completed. If on the other hand it is a RTSTRUCT modality then we need to fill the data in the RTStructureSetInformation and RTStructureROI models. 
# To ensure efficiency, database updates will be done in a single transaction after file metadata has been completely read. 
# After the database transaction has been completed, we will need to store the dicom file using the Pydicom save_as function while ensuring that valid dicom files are generated. This will need to be stored in the application in a directory called processed_dicom_files.

import os
import logging
import re
from typing import Union, List, Dict, Any
from datetime import datetime
from pathlib import Path

import pydicom
from django.db import transaction
from django.conf import settings

from app.models import (
    Patient, DICOMStudy, DICOMSeries, DICOMInstance,
    ImageInformation, RTStructureSetInformation, RTStructureROI,
    GenderChoices
)

logger = logging.getLogger(__name__)

# Modalities that require ImageInformation
IMAGE_MODALITIES = ['CT', 'MR', 'PT', 'PET']
# Modalities that require RTStructureSet processing
RTSTRUCT_MODALITY = 'RTSTRUCT'


def sanitize_path_component(value, default='unknown'):
    """
    Sanitize a string to be safe for use as a directory or filename component.
    Removes or replaces characters that are unsafe for filesystems.
    
    Args:
        value: String to sanitize
        default: Default value if sanitization results in empty string
        
    Returns:
        Sanitized string safe for filesystem use
    """
    if not value:
        return default
    
    # Convert to string and strip whitespace
    sanitized = str(value).strip()
    
    # Replace path separators and other unsafe characters
    # Keep only alphanumeric, dots, hyphens, and underscores
    sanitized = re.sub(r'[^\w\.\-]', '_', sanitized)
    
    # Remove leading/trailing dots and underscores
    sanitized = sanitized.strip('._')
    
    # Limit length to avoid filesystem issues (max 255 chars, but use 200 for safety)
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    
    # Return default if empty after sanitization
    return sanitized if sanitized else default


def get_dicom_value(dataset, tag, default=None):
    """
    Safely extract a value from a DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        tag: DICOM tag name as string
        default: Default value if tag is not present
        
    Returns:
        Value from the dataset or default
    """
    try:
        value = getattr(dataset, tag, default)
        if value is None or value == '':
            return default
        return value
    except Exception:
        return default


def parse_dicom_date(date_string):
    """
    Parse DICOM date string (YYYYMMDD) to Python date object.
    
    Args:
        date_string: DICOM date string
        
    Returns:
        datetime.date object or None
    """
    if not date_string:
        return None
    try:
        return datetime.strptime(str(date_string), '%Y%m%d').date()
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_string}': {e}")
        return None


def map_patient_sex(dicom_sex):
    """
    Map DICOM sex values to GenderChoices.
    
    Args:
        dicom_sex: DICOM PatientSex value (M, F, O)
        
    Returns:
        Mapped gender choice or None
    """
    if not dicom_sex:
        return None
    
    sex_map = {
        'M': GenderChoices.MALE,
        'F': GenderChoices.FEMALE,
        'O': GenderChoices.OTHER,
    }
    return sex_map.get(str(dicom_sex).upper())


def process_patient_data(dataset):
    """
    Extract and save patient information from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        
    Returns:
        Patient model instance
    """
    patient_id = get_dicom_value(dataset, 'PatientID')
    if not patient_id:
        raise ValueError("PatientID is required but not found in DICOM file")
    
    patient_name = get_dicom_value(dataset, 'PatientName', '')
    patient_dob = parse_dicom_date(get_dicom_value(dataset, 'PatientBirthDate'))
    patient_sex = map_patient_sex(get_dicom_value(dataset, 'PatientSex'))
    
    # Update or create patient
    patient, created = Patient.objects.update_or_create(
        unique_patient_id=patient_id,
        defaults={
            'patient_name': str(patient_name),
            'patient_dob': patient_dob,
            'patient_sex': patient_sex,
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} patient: {patient_id}")
    return patient


def process_study_data(dataset, patient):
    """
    Extract and save study information from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        patient: Patient model instance
        
    Returns:
        DICOMStudy model instance
    """
    study_uid = get_dicom_value(dataset, 'StudyInstanceUID')
    if not study_uid:
        raise ValueError("StudyInstanceUID is required but not found in DICOM file")
    
    study_description = get_dicom_value(dataset, 'StudyDescription', '')
    study_date = parse_dicom_date(get_dicom_value(dataset, 'StudyDate'))
    
    # Update or create study
    study, created = DICOMStudy.objects.update_or_create(
        study_instance_uid=study_uid,
        defaults={
            'patient': patient,
            'study_description': study_description,
            'study_date': study_date,
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} study: {study_uid}")
    return study


def process_series_data(dataset, study):
    """
    Extract and save series information from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        study: DICOMStudy model instance
        
    Returns:
        DICOMSeries model instance
    """
    series_uid = get_dicom_value(dataset, 'SeriesInstanceUID')
    if not series_uid:
        raise ValueError("SeriesInstanceUID is required but not found in DICOM file")
    
    frame_of_reference_uid = get_dicom_value(dataset, 'FrameOfReferenceUID', '')
    series_description = get_dicom_value(dataset, 'SeriesDescription', '')
    series_date = parse_dicom_date(get_dicom_value(dataset, 'SeriesDate'))
    
    # Update or create series
    series, created = DICOMSeries.objects.update_or_create(
        series_instance_uid=series_uid,
        defaults={
            'dicom_study': study,
            'frame_of_reference_uid': frame_of_reference_uid,
            'series_description': series_description,
            'series_date': series_date,
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} series: {series_uid}")
    return series


def process_instance_data(dataset, series):
    """
    Extract and save instance information from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset object
        series: DICOMSeries model instance
        
    Returns:
        DICOMInstance model instance
    """
    sop_instance_uid = get_dicom_value(dataset, 'SOPInstanceUID')
    if not sop_instance_uid:
        raise ValueError("SOPInstanceUID is required but not found in DICOM file")
    
    modality = get_dicom_value(dataset, 'Modality', '')
    pixel_spacing = get_dicom_value(dataset, 'PixelSpacing', '')
    
    # Update or create instance
    instance, created = DICOMInstance.objects.update_or_create(
        sop_instance_uid=sop_instance_uid,
        defaults={
            'dicom_series': series,
            'modality': modality,
            'pixel_spacing': str(pixel_spacing) if pixel_spacing else '',
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} instance: {sop_instance_uid}")
    return instance


def process_image_information(dataset, instance):
    """
    Extract and save image-specific information for CT/MR/PET modalities.
    
    Args:
        dataset: pydicom Dataset object
        instance: DICOMInstance model instance
    """
    slice_location = get_dicom_value(dataset, 'SliceLocation')
    pixel_spacing = get_dicom_value(dataset, 'PixelSpacing')
    slice_thickness = get_dicom_value(dataset, 'SliceThickness')
    patient_position = get_dicom_value(dataset, 'PatientPosition', '')
    image_position_patient = get_dicom_value(dataset, 'ImagePositionPatient')
    image_orientation_patient = get_dicom_value(dataset, 'ImageOrientationPatient')
    instance_number = get_dicom_value(dataset, 'InstanceNumber')
    
    # Convert to appropriate types for JSON storage
    pixel_spacing_json = list(pixel_spacing) if pixel_spacing else None
    image_position_json = list(image_position_patient) if image_position_patient else None
    image_orientation_json = list(image_orientation_patient) if image_orientation_patient else None
    
    # Update or create image information
    image_info, created = ImageInformation.objects.update_or_create(
        dicom_instance=instance,
        defaults={
            'slice_location': slice_location,
            'pixel_spacing': pixel_spacing_json,
            'slice_thickness': slice_thickness,
            'patient_position': patient_position,
            'image_position_patient': image_position_json,
            'image_orientation_patient': image_orientation_json,
            'instance_number': instance_number,
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} image information for instance: {instance.sop_instance_uid}")


def process_rtstruct_information(dataset, instance):
    """
    Extract and save RTStructureSet information.
    
    Args:
        dataset: pydicom Dataset object
        instance: DICOMInstance model instance
    """
    # Get number of ROIs
    structure_set_roi_sequence = get_dicom_value(dataset, 'StructureSetROISequence', [])
    number_of_roi = len(structure_set_roi_sequence) if structure_set_roi_sequence else 0
    
    # Get referenced frame of reference UID
    referenced_frame_of_reference_uid = ''
    referenced_frame_of_reference_sequence = get_dicom_value(dataset, 'ReferencedFrameOfReferenceSequence')
    if referenced_frame_of_reference_sequence and len(referenced_frame_of_reference_sequence) > 0:
        referenced_frame_of_reference_uid = get_dicom_value(
            referenced_frame_of_reference_sequence[0], 
            'FrameOfReferenceUID', 
            ''
        )
    
    # Update or create RTStructureSet information
    rtstruct_info, created = RTStructureSetInformation.objects.update_or_create(
        dicom_instance=instance,
        defaults={
            'number_of_roi': number_of_roi,
            'referenced_frame_of_reference_uid': referenced_frame_of_reference_uid,
            'prescription_template_id': None,  # Will be matched later by rules
        }
    )
    
    logger.info(f"{'Created' if created else 'Updated'} RTStructureSet information for instance: {instance.sop_instance_uid}")
    
    # Process individual ROIs
    process_rtstruct_rois(dataset, rtstruct_info)


def process_rtstruct_rois(dataset, rtstruct_info):
    """
    Extract and save individual ROI information from RTStructureSet.
    
    Args:
        dataset: pydicom Dataset object
        rtstruct_info: RTStructureSetInformation model instance
    """
    structure_set_roi_sequence = get_dicom_value(dataset, 'StructureSetROISequence', [])
    roi_contour_sequence = get_dicom_value(dataset, 'ROIContourSequence', [])
    
    # Create a mapping of ROI numbers to contour data
    roi_contour_map = {}
    for contour_item in roi_contour_sequence:
        roi_number = get_dicom_value(contour_item, 'ReferencedROINumber')
        contour_sequence = get_dicom_value(contour_item, 'ContourSequence', [])
        
        contour_data_list = []
        for contour in contour_sequence:
            contour_data = get_dicom_value(contour, 'ContourData', [])
            
            # Get referenced SOP instance UID
            contour_image_sequence = get_dicom_value(contour, 'ContourImageSequence', [])
            referenced_sop_uid = ''
            if contour_image_sequence and len(contour_image_sequence) > 0:
                referenced_sop_uid = get_dicom_value(
                    contour_image_sequence[0], 
                    'ReferencedSOPInstanceUID', 
                    ''
                )
            
            if contour_data:
                contour_data_list.append({
                    'contour_data': list(contour_data),
                    'referenced_sop_instance_uid': referenced_sop_uid
                })
        
        roi_contour_map[roi_number] = contour_data_list
    
    # Process each ROI
    for roi_item in structure_set_roi_sequence:
        roi_number = get_dicom_value(roi_item, 'ROINumber')
        roi_name = get_dicom_value(roi_item, 'ROIName', '')
        
        # Get contour data for this ROI
        roi_contour_data = roi_contour_map.get(roi_number, [])
        
        # Update or create ROI
        roi, created = RTStructureROI.objects.update_or_create(
            rt_structure_set=rtstruct_info,
            roi_number=roi_number,
            defaults={
                'roi_name': roi_name,
                'roi_contour_data': roi_contour_data,
            }
        )
        
        logger.debug(f"{'Created' if created else 'Updated'} ROI: {roi_name} (Number: {roi_number})")


def save_processed_dicom_file(dataset, original_file_path, sop_instance_uid):
    """
    Save the processed DICOM file to the processed_dicom_files directory.
    Files are organized by Patient ID, Study UID, and Series UID for better filesystem organization.
    All path components are sanitized to ensure filesystem safety.
    
    Args:
        dataset: pydicom Dataset object
        original_file_path: Original file path
        sop_instance_uid: SOP Instance UID for naming
        
    Returns:
        Path to saved file
    """
    # Get Patient ID, Study UID, and Series UID for directory organization
    patient_id = get_dicom_value(dataset, 'PatientID', 'unknown_patient')
    study_uid = get_dicom_value(dataset, 'StudyInstanceUID', 'unknown_study')
    series_uid = get_dicom_value(dataset, 'SeriesInstanceUID', 'unknown_series')
    
    # Sanitize all path components to ensure filesystem safety
    patient_id_safe = sanitize_path_component(patient_id, 'unknown_patient')
    study_uid_safe = sanitize_path_component(study_uid, 'unknown_study')
    series_uid_safe = sanitize_path_component(series_uid, 'unknown_series')
    sop_instance_uid_safe = sanitize_path_component(sop_instance_uid, 'unknown_instance')
    
    # Create organized directory structure: processed_dicom_files/patient_id/study_uid/series_uid/
    processed_dir = os.path.join(
        settings.BASE_DIR, 
        'processed_dicom_files',
        patient_id_safe,
        study_uid_safe,
        series_uid_safe
    )
    os.makedirs(processed_dir, exist_ok=True)
    
    # Generate filename using sanitized SOP Instance UID
    filename = f"{sop_instance_uid_safe}.dcm"
    output_path = os.path.join(processed_dir, filename)
    
    # Save the DICOM file
    try:
        dataset.save_as(output_path, write_like_original=False)
        logger.info(f"Saved processed DICOM file: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to save DICOM file {output_path}: {e}")
        raise


def process_single_dicom_file(file_path: str) -> Dict[str, Any]:
    """
    Process a single DICOM file and extract metadata.
    
    Args:
        file_path: Path to the DICOM file
        
    Returns:
        Dictionary with processing results
    """
    result = {
        'file_path': file_path,
        'success': False,
        'error': None,
        'sop_instance_uid': None,
        'modality': None,
    }
    
    try:
        # Read DICOM file with force=True
        logger.info(f"Processing DICOM file: {file_path}")
        dataset = pydicom.dcmread(file_path, force=True)
        
        # Check if Modality tag is present
        modality = get_dicom_value(dataset, 'Modality')
        if not modality:
            logger.warning(f"Skipping file {file_path}: Modality tag not present")
            result['error'] = "Modality tag not present"
            return result
        
        result['modality'] = modality
        
        # Process within a transaction for efficiency
        with transaction.atomic():
            # Process patient, study, series, and instance data
            patient = process_patient_data(dataset)
            study = process_study_data(dataset, patient)
            series = process_series_data(dataset, study)
            instance = process_instance_data(dataset, series)
            
            result['sop_instance_uid'] = instance.sop_instance_uid
            
            # Process modality-specific information
            if modality in IMAGE_MODALITIES:
                process_image_information(dataset, instance)
            elif modality == RTSTRUCT_MODALITY:
                process_rtstruct_information(dataset, instance)
            else:
                logger.info(f"Modality {modality} does not require additional processing")
        
        # Save processed DICOM file after transaction completes
        save_processed_dicom_file(dataset, file_path, instance.sop_instance_uid)
        
        result['success'] = True
        logger.info(f"Successfully processed DICOM file: {file_path}")
        
    except Exception as e:
        logger.error(f"Error processing DICOM file {file_path}: {e}", exc_info=True)
        result['error'] = str(e)
    
    return result


def process_dicom_files(file_paths: Union[str, List[str]]) -> Dict[str, Any]:
    """
    Process DICOM files and extract metadata.
    Can handle either a single file path or a list of file paths.
    
    Args:
        file_paths: Single file path string or list of file paths
        
    Returns:
        Dictionary with processing results for all files
    """
    # Ensure file_paths is a list
    if isinstance(file_paths, str):
        file_paths = [file_paths]
    
    logger.info(f"Starting DICOM processing for {len(file_paths)} files")
    
    results = {
        'total_files': len(file_paths),
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'file_results': []
    }
    
    # Process each file sequentially
    for idx, file_path in enumerate(file_paths, 1):
        logger.info(f"Processing file {idx}/{len(file_paths)}: {file_path}")
        
        file_result = process_single_dicom_file(file_path)
        results['file_results'].append(file_result)
        
        if file_result['success']:
            results['successful'] += 1
        elif file_result['error'] == "Modality tag not present":
            results['skipped'] += 1
        else:
            results['failed'] += 1
    
    logger.info(
        f"DICOM processing completed. "
        f"Successful: {results['successful']}, "
        f"Failed: {results['failed']}, "
        f"Skipped: {results['skipped']}"
    )
    
    return results
