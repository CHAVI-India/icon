# DICOM Processing System - Setup Guide

## Overview
This system processes DICOM files uploaded as ZIP archives through the Django admin interface with real-time progress tracking using Celery and celery-progress.

## Components Created

### 1. Celery Tasks (`app/tasks.py`)
- **`process_dicom_file_task(dicom_file_id)`**: Main task that orchestrates the entire workflow
  - Extracts ZIP archive
  - Processes DICOM files
  - Updates database
  - Tracks progress using ProgressRecorder
  
- **`process_multiple_dicom_files(dicom_file_ids)`**: Batch processing for multiple files

### 2. Admin Interface (`app/admin.py`)
- **DICOMFileAdmin**: Enhanced admin with:
  - "Process Now" button for individual files
  - "Process selected DICOM files" bulk action
  - Status indicators (Pending, In Progress, Completed, Failed)
  - All models registered with appropriate filters and search

### 3. Views (`app/views.py`)
- **`process_dicom_file_view`**: Starts processing and redirects to progress page
- **`dicom_processing_progress`**: Displays progress page with Bootstrap UI
- **`task_status`**: API endpoint for real-time progress updates (JSON)

### 4. URL Configuration
- **`app/urls.py`**: App-specific URLs
- **`icon/urls.py`**: Includes app URLs under `/dicom/` prefix

### 5. Templates (Bootstrap 5)
- **`base.html`**: Base template with Bootstrap 5 and icons
- **`processing_progress.html`**: Real-time progress tracking with:
  - Animated progress bars
  - Status badges
  - Auto-updating via AJAX (polls every 1 second)
  - Results display on completion
  
- **`processing_error.html`**: Error display page

## How to Use

### From Django Admin:

1. **Upload DICOM Files**:
   - Go to `/admin/app/dicomfile/`
   - Click "Add DICOM File"
   - Upload a ZIP file containing DICOM files
   - Save

2. **Process Single File**:
   - Click the "Process Now" button next to a pending file
   - Redirects to progress page automatically

3. **Process Multiple Files**:
   - Select multiple pending files using checkboxes
   - Choose "Process selected DICOM files" from Actions dropdown
   - Click "Go"
   - Redirects to progress page showing all tasks

### Progress Page Features:
- Real-time progress updates
- Current step description
- Percentage completion
- Success/failure indicators
- Detailed results on completion

## File Organization

Processed DICOM files are saved to:
```
processed_dicom_files/
├── {patient_id}/
│   ├── {study_uid}/
│   │   ├── {series_uid}/
│   │   │   ├── {sop_instance_uid}.dcm
```

All path components are sanitized for filesystem safety.

## Database Updates

The system automatically creates/updates:
- **Patient** records
- **DICOMStudy** records
- **DICOMSeries** records
- **DICOMInstance** records
- **ImageInformation** (for CT/MR/PET)
- **RTStructureSetInformation** and **RTStructureROI** (for RTSTRUCT)

## Task Workflow

1. **Initialize** (0-10%): Load DICOMFile, update status to IN_PROGRESS
2. **Extract** (10-30%): Extract ZIP archive to temp directory
3. **Process** (30-90%): Process each DICOM file sequentially
4. **Cleanup** (90-95%): Remove temporary files
5. **Finalize** (95-100%): Update status to COMPLETED, save logs

## Error Handling

- Automatic status updates on failure
- Temp directory cleanup on errors
- Detailed error messages in progress page
- Processing logs stored in `processing_log_data` field

## Next Steps

1. **Start Celery Worker**:
   ```bash
   celery -A icon worker -l info
   ```

2. **Start Celery Beat** (if using scheduled tasks):
   ```bash
   celery -A icon beat -l info
   ```

3. **Run Django Development Server**:
   ```bash
   python manage.py runserver
   ```

4. **Access Admin**:
   - Navigate to `http://localhost:8000/admin/`
   - Upload and process DICOM files

## Configuration Notes

- Progress updates every 1 second (configurable in template)
- Uses Django database as Celery result backend
- Requires `celery-progress` package (already in requirements.txt)
- All views require staff member authentication

## Troubleshooting

- **No progress updates**: Ensure Celery worker is running
- **Tasks stuck in PENDING**: Check Celery broker connection
- **Import errors**: Run `python manage.py migrate` if needed
- **Template not found**: Ensure `app` is in `INSTALLED_APPS`
