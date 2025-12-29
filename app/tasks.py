import logging
from celery import shared_task, chain
from celery_progress.backend import ProgressRecorder
from django.utils import timezone

from app.models import DICOMFile, ProcessingStatus
from app.utilities.extract_dicom_form_zip import (
    extract_dicom_from_dicomfile_instance,
    cleanup_temp_directory
)
from app.utilities.process_dicom import process_dicom_files

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def process_dicom_file_task(self, dicom_file_id):
    """
    Celery task chain to extract and process DICOM files from a ZIP archive.
    This task orchestrates the entire workflow with progress tracking.
    
    Args:
        dicom_file_id: ID of the DICOMFile model instance
        
    Returns:
        Dictionary with processing results
    """
    progress_recorder = ProgressRecorder(self)
    temp_dir = None
    
    try:
        # Get the DICOMFile instance
        progress_recorder.set_progress(0, 100, description="Initializing...")
        dicom_file = DICOMFile.objects.get(id=dicom_file_id)
        
        # Update status to in_progress
        dicom_file.processing_status = ProcessingStatus.IN_PROGRESS
        dicom_file.save()
        
        logger.info(f"Starting processing for DICOMFile ID: {dicom_file_id}")
        
        # Step 1: Extract ZIP file
        progress_recorder.set_progress(10, 100, description="Extracting ZIP archive...")
        logger.info("Extracting DICOM files from ZIP archive")
        
        temp_dir, dicom_files = extract_dicom_from_dicomfile_instance(dicom_file)
        
        logger.info(f"Extracted {len(dicom_files)} files from ZIP archive")
        progress_recorder.set_progress(30, 100, description=f"Extracted {len(dicom_files)} files")
        
        # Step 2: Process DICOM files
        progress_recorder.set_progress(40, 100, description="Processing DICOM files...")
        logger.info(f"Processing {len(dicom_files)} DICOM files")
        
        # Process files with progress updates
        results = {
            'total_files': len(dicom_files),
            'successful': 0,
            'failed': 0,
            'skipped': 0,
            'file_results': []
        }
        
        for idx, file_path in enumerate(dicom_files, 1):
            # Calculate progress (40% to 90% range for processing)
            progress_percent = 40 + int((idx / len(dicom_files)) * 50)
            progress_recorder.set_progress(
                progress_percent, 
                100, 
                description=f"Processing file {idx}/{len(dicom_files)}"
            )
            
            # Import here to avoid circular imports
            from app.utilities.process_dicom import process_single_dicom_file
            
            file_result = process_single_dicom_file(file_path)
            results['file_results'].append(file_result)
            
            if file_result['success']:
                results['successful'] += 1
            elif file_result.get('error') == "Modality tag not present":
                results['skipped'] += 1
            else:
                results['failed'] += 1
        
        # Step 3: Cleanup
        progress_recorder.set_progress(95, 100, description="Cleaning up temporary files...")
        logger.info("Cleaning up temporary directory")
        cleanup_temp_directory(temp_dir)
        
        # Step 4: Update DICOMFile status
        progress_recorder.set_progress(98, 100, description="Finalizing...")
        
        dicom_file.processing_status = ProcessingStatus.COMPLETED
        dicom_file.date_processing_completed = timezone.now()
        dicom_file.processing_log_data = {
            'total_files': results['total_files'],
            'successful': results['successful'],
            'failed': results['failed'],
            'skipped': results['skipped'],
            'completed_at': timezone.now().isoformat()
        }
        dicom_file.save()
        
        logger.info(
            f"Processing completed for DICOMFile ID: {dicom_file_id}. "
            f"Successful: {results['successful']}, Failed: {results['failed']}, "
            f"Skipped: {results['skipped']}"
        )
        
        progress_recorder.set_progress(
            100, 
            100, 
            description=f"Completed! Processed {results['successful']}/{results['total_files']} files successfully"
        )
        
        return {
            'status': 'completed',
            'dicom_file_id': dicom_file_id,
            'results': results
        }
        
    except DICOMFile.DoesNotExist:
        error_msg = f"DICOMFile with ID {dicom_file_id} does not exist"
        logger.error(error_msg)
        progress_recorder.set_progress(100, 100, description=f"Error: {error_msg}")
        return {
            'status': 'failed',
            'error': error_msg
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing DICOMFile ID {dicom_file_id}: {error_msg}", exc_info=True)
        
        # Update status to failed
        try:
            dicom_file = DICOMFile.objects.get(id=dicom_file_id)
            dicom_file.processing_status = ProcessingStatus.FAILED
            dicom_file.processing_log_data = {
                'error': error_msg,
                'failed_at': timezone.now().isoformat()
            }
            dicom_file.save()
        except Exception:
            pass
        
        # Cleanup temp directory if it exists
        if temp_dir:
            try:
                cleanup_temp_directory(temp_dir)
            except Exception:
                pass
        
        progress_recorder.set_progress(100, 100, description=f"Error: {error_msg}")
        
        return {
            'status': 'failed',
            'error': error_msg
        }


@shared_task
def process_multiple_dicom_files(dicom_file_ids):
    """
    Process multiple DICOM files in sequence.
    
    Args:
        dicom_file_ids: List of DICOMFile IDs to process
        
    Returns:
        List of task IDs
    """
    task_ids = []
    for dicom_file_id in dicom_file_ids:
        task = process_dicom_file_task.delay(dicom_file_id)
        task_ids.append(task.id)
    
    return task_ids
