# This function will extract all files from an uploaded ZIP file into a temporary directory and return the path of the files extracted from the zip file. If the files are present inside nested subdirectories it will unnest them during the extraction process. 

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


def extract_dicom_from_zip(zip_file_path: str) -> Tuple[str, List[str]]:
    """
    Extract all files from a ZIP archive into a temporary directory.
    Flattens nested directory structures during extraction.
    
    Args:
        zip_file_path: Path to the ZIP file to extract
        
    Returns:
        Tuple containing:
            - temp_dir: Path to the temporary directory containing extracted files
            - dicom_files: List of paths to extracted DICOM files
            
    Raises:
        zipfile.BadZipFile: If the file is not a valid ZIP archive
        Exception: For other extraction errors
    """
    # Create a temporary directory for extraction
    temp_dir = tempfile.mkdtemp(prefix='dicom_extract_')
    dicom_files = []
    
    try:
        logger.info(f"Extracting ZIP file: {zip_file_path}")
        
        with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
            # Get list of all files in the archive
            file_list = zip_ref.namelist()
            logger.info(f"Found {len(file_list)} items in ZIP archive")
            
            for file_info in zip_ref.infolist():
                # Skip directories
                if file_info.is_dir():
                    continue
                
                # Skip hidden files and system files (like __MACOSX)
                filename = os.path.basename(file_info.filename)
                if filename.startswith('.') or '__MACOSX' in file_info.filename:
                    logger.debug(f"Skipping system/hidden file: {file_info.filename}")
                    continue
                
                # Extract file content
                file_data = zip_ref.read(file_info.filename)
                
                # Create flattened filename (use only the basename)
                # If there are duplicate filenames, append a counter
                target_filename = filename
                target_path = os.path.join(temp_dir, target_filename)
                
                # Handle duplicate filenames by appending a counter
                counter = 1
                while os.path.exists(target_path):
                    name, ext = os.path.splitext(filename)
                    target_filename = f"{name}_{counter}{ext}"
                    target_path = os.path.join(temp_dir, target_filename)
                    counter += 1
                
                # Write the file to the temporary directory
                with open(target_path, 'wb') as f:
                    f.write(file_data)
                
                dicom_files.append(target_path)
                logger.debug(f"Extracted: {file_info.filename} -> {target_filename}")
        
        logger.info(f"Successfully extracted {len(dicom_files)} files to {temp_dir}")
        return temp_dir, dicom_files
        
    except zipfile.BadZipFile as e:
        logger.error(f"Invalid ZIP file: {zip_file_path}")
        # Clean up temporary directory on error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise
    except Exception as e:
        logger.error(f"Error extracting ZIP file: {str(e)}")
        # Clean up temporary directory on error
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        raise


def cleanup_temp_directory(temp_dir: str) -> None:
    """
    Clean up the temporary directory after processing.
    
    Args:
        temp_dir: Path to the temporary directory to remove
    """
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logger.error(f"Error cleaning up temporary directory {temp_dir}: {str(e)}")


def extract_dicom_from_dicomfile_instance(dicom_file_instance):
    """
    Extract DICOM files from a DICOMFile model instance.
    This is a convenience function that works directly with Django model instances.
    
    Args:
        dicom_file_instance: Instance of DICOMFile model
        
    Returns:
        Tuple containing:
            - temp_dir: Path to the temporary directory containing extracted files
            - dicom_files: List of paths to extracted DICOM files
    """
    # Get the file path from the FileField
    zip_file_path = dicom_file_instance.file.path
    
    if not os.path.exists(zip_file_path):
        raise FileNotFoundError(f"ZIP file not found: {zip_file_path}")
    
    return extract_dicom_from_zip(zip_file_path)
