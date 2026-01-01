from celery import shared_task
from celery_progress.backend import ProgressRecorder
from trainer.dicom_processor.training_data_preparation import (
    extract_archive,
    get_all_dicom_files,
    organize_dicom_data,
    save_image_data_to_db,
    save_rtstruct_data_to_db,
    save_rtplan_rtdose_data_to_db,
    organize_files_by_structure
)
import os


@shared_task(bind=True)
def process_training_data_archive_task(self, archive_id, extraction_base_path='/tmp/training_data'):
    progress_recorder = ProgressRecorder(self)
    
    try:
        progress_recorder.set_progress(0, 100, description="Starting archive extraction...")
        
        extraction_path = os.path.join(extraction_base_path, f'archive_{archive_id}')
        os.makedirs(extraction_path, exist_ok=True)
        
        success, result = extract_archive(archive_id, extraction_path)
        if not success:
            return {
                'success': False,
                'error': f"Failed to extract archive: {result}"
            }
        
        progress_recorder.set_progress(10, 100, description="Archive extracted. Scanning for DICOM files...")
        
        dicom_files = get_all_dicom_files(extraction_path)
        
        if not dicom_files:
            return {
                'success': False,
                'error': "No files found in the archive"
            }
        
        total_files = len(dicom_files)
        progress_recorder.set_progress(15, 100, description=f"Found {total_files} files. Reading DICOM metadata...")
        
        image_data, rtstruct_data, rtplan_data, rtdose_data = organize_dicom_data(dicom_files)
        
        progress_recorder.set_progress(40, 100, description=f"Metadata extracted. Organizing files into structured directories...")
        
        organized_path, organized_image_paths, organized_rtstruct_paths, organized_rtplan_paths, organized_rtdose_paths = organize_files_by_structure(
            archive_id, image_data, rtstruct_data, rtplan_data, rtdose_data
        )
        
        progress_recorder.set_progress(60, 100, description=f"Files organized. Saving {len(image_data)} image series to database...")
        
        created_images = save_image_data_to_db(archive_id, image_data, organized_image_paths)
        
        progress_recorder.set_progress(75, 100, description=f"Saved {len(created_images)} image series. Saving {len(rtstruct_data)} RT Structure Sets...")
        
        created_rtstructs = save_rtstruct_data_to_db(rtstruct_data, created_images, organized_rtstruct_paths)
        
        progress_recorder.set_progress(90, 100, description=f"Saved {len(created_rtstructs)} RT Structure Sets. Saving RT Plans and Doses...")
        
        save_rtplan_rtdose_data_to_db(rtplan_data, rtdose_data, created_rtstructs, organized_rtplan_paths, organized_rtdose_paths)
        
        progress_recorder.set_progress(100, 100, description="Processing complete!")
        
        return {
            'success': True,
            'images_count': len(created_images),
            'rtstructs_count': len(created_rtstructs),
            'total_files_processed': total_files,
            'rtplan_count': len(rtplan_data),
            'rtdose_count': len(rtdose_data),
            'organized_path': organized_path
        }
    
    except Exception as e:
        progress_recorder.set_progress(0, 100, description=f"Error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
