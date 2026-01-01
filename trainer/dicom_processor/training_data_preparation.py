'''
This file will contain functions that will properly prepare the training data for model training. The user will upload an archive containing the DICOM files which will need to be processed. The file upload will occur using the TrainingDataSetArchive model. 


When the user extracts the archive for processing, the system will go through each file in the archive, including those nested into subdirectories. The following will be the processing steps:

1. Read the file using Pydicom. We will use Force=True option to ensure that the file gets read. Stop before pixel will used to speed up the process and reduce the memory usage.
2. Check if the file has a modality tag. If it does not have the modality tag then the file will not be procesed further. Check if the modality fits any of the following categories:
 - Image files : CT / MR / PT
 - RT Structure Set files : RTSTRUCT
 - RT Plan and Dose files : RTPLAN  and RT Dose

3. If the file is an image type file it will be processed further. If the system encounters a RT STRuctureSet file it will be processed after the RT image files belonging to the series have been evaluated. Similiarly the RT Plan and RT Dose files will be processed only after the RTStructureSet file has been processed.

4. Processing the files will involve reading the Series Instance UID, Patient ID, series description and series acquisition date for image files. This information will be collected and sorted such that the files belonging to a specific series are first grouped together. For RTStructureSet file we will need to read the Referenced Series Instance UID tag to link the RTStructureSet file with the corresponding image. Addditionally we will need to note the series instance UID of the RTStructureSet file. This will be followed by reading the ROI names from the RTStructureSet file. For RT Plan and Dose files we will need to read the Referenced RT Plan Sequence > Referenced SOP Instance UID tag to link the RTPlan and RTDose files with the corresponding RTStructureSet file. 

5. After the information has been read from all files, the database will be populated with the information :
 - Image files : TrainingImage model
 - RT Structure Set files : TrainingRTStructureSetFile model
 - ROIs : TrainingRTStructureSetROI model
 - RT Plan and Dose files : TrainingRTPlanAndDoseFile model

6. The archive can contain images of multiple patients and each series of images can have multiple strcutresets. Similiarly structuresets may have multiple linked plans and respective doses. 

'''

import os
import zipfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import pydicom
from django.utils import timezone
from trainer.models import (
    TrainingDataSetArchive,
    TrainingImage,
    TrainingRTStructureSetFile,
    TrainingRTStructureSetROI,
    TrainingRTPlanAndDoseFile,
    ImageTypeChoices
)


def extract_archive(archive_id, extraction_path):
    try:
        archive = TrainingDataSetArchive.objects.get(id=archive_id)
        archive_file_path = archive.file.path
        
        with zipfile.ZipFile(archive_file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_path)
        
        archive.archive_extracted = True
        archive.date_archive_extracted = timezone.now()
        archive.save()
        
        return True, extraction_path
    except Exception as e:
        return False, str(e)


def get_all_dicom_files(directory):
    dicom_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            dicom_files.append(file_path)
    return dicom_files


def read_dicom_metadata(file_path):
    try:
        dcm = pydicom.dcmread(file_path, force=True, stop_before_pixels=True)
        
        if not hasattr(dcm, 'Modality'):
            return None
        
        modality = dcm.Modality
        
        metadata = {
            'file_path': file_path,
            'modality': modality
        }
        
        if modality in ['CT', 'MR', 'PT']:
            metadata.update({
                'series_instance_uid': getattr(dcm, 'SeriesInstanceUID', None),
                'patient_id': getattr(dcm, 'PatientID', None),
                'series_description': getattr(dcm, 'SeriesDescription', None),
                'series_date': getattr(dcm, 'SeriesDate', None),
            })
        
        elif modality == 'RTSTRUCT':
            metadata['structureset_series_uid'] = getattr(dcm, 'SeriesInstanceUID', None)
            
            try:
                ref_frame_of_ref_seq = dcm.ReferencedFrameOfReferenceSequence[0]
                rt_ref_study_seq = ref_frame_of_ref_seq.RTReferencedStudySequence[0]
                rt_ref_series_seq = rt_ref_study_seq.RTReferencedSeriesSequence[0]
                metadata['referenced_series_uid'] = rt_ref_series_seq.SeriesInstanceUID
            except (AttributeError, IndexError):
                metadata['referenced_series_uid'] = None
            
            roi_names = []
            if hasattr(dcm, 'StructureSetROISequence'):
                for roi in dcm.StructureSetROISequence:
                    if hasattr(roi, 'ROIName'):
                        roi_names.append(roi.ROIName)
            metadata['roi_names'] = roi_names
        
        elif modality == 'RTPLAN':
            metadata['rtplan_series_uid'] = getattr(dcm, 'SeriesInstanceUID', None)
            metadata['rtplan_sop_instance_uid'] = getattr(dcm, 'SOPInstanceUID', None)
            
            try:
                ref_struct_set_seq = dcm.ReferencedStructureSetSequence[0]
                metadata['referenced_structureset_sop_uid'] = ref_struct_set_seq.ReferencedSOPInstanceUID
            except (AttributeError, IndexError):
                metadata['referenced_structureset_sop_uid'] = None
        
        elif modality == 'RTDOSE':
            metadata['rtdose_series_uid'] = getattr(dcm, 'SeriesInstanceUID', None)
            
            try:
                ref_rt_plan_seq = dcm.ReferencedRTPlanSequence[0]
                metadata['referenced_rtplan_sop_uid'] = ref_rt_plan_seq.ReferencedSOPInstanceUID
            except (AttributeError, IndexError):
                metadata['referenced_rtplan_sop_uid'] = None
        
        return metadata
    
    except Exception as e:
        return None


def organize_dicom_data(dicom_files):
    image_data = defaultdict(list)
    rtstruct_data = []
    rtplan_data = []
    rtdose_data = []
    
    for file_path in dicom_files:
        metadata = read_dicom_metadata(file_path)
        
        if metadata is None:
            continue
        
        modality = metadata['modality']
        
        if modality in ['CT', 'MR', 'PT']:
            series_uid = metadata.get('series_instance_uid')
            if series_uid:
                image_data[series_uid].append(metadata)
        
        elif modality == 'RTSTRUCT':
            rtstruct_data.append(metadata)
        
        elif modality == 'RTPLAN':
            rtplan_data.append(metadata)
        
        elif modality == 'RTDOSE':
            rtdose_data.append(metadata)
    
    return image_data, rtstruct_data, rtplan_data, rtdose_data


def save_image_data_to_db(archive_id, image_data, organized_image_paths=None):
    archive = TrainingDataSetArchive.objects.get(id=archive_id)
    created_images = {}
    
    for series_uid, images in image_data.items():
        if not images:
            continue
        first_image = images[0]
        image_type = first_image.get('modality', '').lower()
        
        series_date = None
        if first_image.get('series_date'):
            try:
                series_date = datetime.strptime(first_image['series_date'], '%Y%m%d').date()
            except:
                pass
        
        if organized_image_paths and series_uid in organized_image_paths:
            image_paths = organized_image_paths[series_uid]
        else:
            image_paths = [img['file_path'] for img in images]
        
        modality = first_image['modality'].lower()
        image_type = None
        if modality == 'ct':
            image_type = ImageTypeChoices.CT
        elif modality == 'mr':
            image_type = ImageTypeChoices.MR
        elif modality == 'pt':
            image_type = ImageTypeChoices.PT
        
        training_image, created = TrainingImage.objects.update_or_create(
            dicom_series_uid=series_uid,
            defaults={
                'training_data_set_archive': archive,
                'number_of_images': len(images),
                'patient_id': first_image.get('patient_id'),
                'series_description': first_image.get('series_description'),
                'series_acquisition_date': series_date,
                'image_type': image_type,
                'image_paths': image_paths,
            }
        )
        
        created_images[series_uid] = training_image
    
    return created_images


def save_rtstruct_data_to_db(rtstruct_data, created_images, organized_rtstruct_paths=None):
    created_rtstructs = {}
    
    for rtstruct in rtstruct_data:
        referenced_series_uid = rtstruct.get('referenced_series_uid')
        structureset_series_uid = rtstruct.get('structureset_series_uid')
        
        if not referenced_series_uid or not structureset_series_uid:
            continue
        
        training_image = created_images.get(referenced_series_uid)
        if not training_image:
            try:
                training_image = TrainingImage.objects.get(dicom_series_uid=referenced_series_uid)
            except TrainingImage.DoesNotExist:
                continue
        
        if organized_rtstruct_paths and structureset_series_uid in organized_rtstruct_paths:
            struct_path = organized_rtstruct_paths[structureset_series_uid]
        else:
            struct_path = rtstruct['file_path']
        
        rt_struct, created = TrainingRTStructureSetFile.objects.update_or_create(
            structureset_dicom_series_uid=structureset_series_uid,
            defaults={
                'referenced_series_instance_uid': training_image,
                'structureset_path': struct_path,
            }
        )
        
        created_rtstructs[structureset_series_uid] = rt_struct
        
        for roi_name in rtstruct.get('roi_names', []):
            TrainingRTStructureSetROI.objects.get_or_create(
                training_rt_structure_set=rt_struct,
                roi_name=roi_name
            )
    
    return created_rtstructs


def save_rtplan_rtdose_data_to_db(rtplan_data, rtdose_data, created_rtstructs, organized_rtplan_paths=None, organized_rtdose_paths=None):
    rtplan_by_sop = {}
    for rtplan in rtplan_data:
        sop_uid = rtplan.get('rtplan_sop_instance_uid')
        if sop_uid:
            rtplan_by_sop[sop_uid] = rtplan
    
    for rtdose in rtdose_data:
        referenced_rtplan_sop = rtdose.get('referenced_rtplan_sop_uid')
        
        if not referenced_rtplan_sop:
            continue
        
        rtplan = rtplan_by_sop.get(referenced_rtplan_sop)
        if not rtplan:
            continue
        
        referenced_structureset_sop = rtplan.get('referenced_structureset_sop_uid')
        if not referenced_structureset_sop:
            continue
        
        rt_struct = None
        for struct_uid, struct_obj in created_rtstructs.items():
            try:
                dcm = pydicom.dcmread(struct_obj.structureset_path, force=True, stop_before_pixels=True)
                if hasattr(dcm, 'SOPInstanceUID') and dcm.SOPInstanceUID == referenced_structureset_sop:
                    rt_struct = struct_obj
                    break
            except:
                continue
        
        if not rt_struct:
            continue
        
        rtplan_series_uid = rtplan.get('rtplan_series_uid')
        rtdose_series_uid = rtdose.get('rtdose_series_uid')
        
        if organized_rtplan_paths and rtplan_series_uid in organized_rtplan_paths:
            plan_path = organized_rtplan_paths[rtplan_series_uid]
        else:
            plan_path = rtplan['file_path']
        
        if organized_rtdose_paths and rtdose_series_uid in organized_rtdose_paths:
            dose_path = organized_rtdose_paths[rtdose_series_uid]
        else:
            dose_path = rtdose['file_path']
        
        TrainingRTPlanAndDoseFile.objects.update_or_create(
            rtdose_series_instance_uid=rtdose_series_uid,
            rtplan_series_instance_uid=rtplan_series_uid,
            defaults={
                'structureset_referenced_series_intance_uid': rt_struct,
                'rtdose_path': dose_path,
                'rtplan_path': plan_path,
            }
        )


def organize_files_by_structure(archive_id, image_data, rtstruct_data, rtplan_data, rtdose_data, organized_base_path=None):
    from django.conf import settings
    
    if organized_base_path is None:
        organized_base_path = os.path.join(settings.MEDIA_ROOT, 'training_data_organized')
    
    archive = TrainingDataSetArchive.objects.get(id=archive_id)
    organized_path = os.path.join(organized_base_path, f'archive_{archive_id}')
    os.makedirs(organized_path, exist_ok=True)
    
    series_to_sop_mapping = {}
    organized_image_paths = {}
    organized_rtstruct_paths = {}
    organized_rtplan_paths = {}
    organized_rtdose_paths = {}
    
    for series_uid, images in image_data.items():
        series_dir = os.path.join(organized_path, series_uid)
        os.makedirs(series_dir, exist_ok=True)
        
        if series_uid not in organized_image_paths:
            organized_image_paths[series_uid] = []
        
        for img_metadata in images:
            try:
                dcm = pydicom.dcmread(img_metadata['file_path'], force=True)
                sop_instance_uid = getattr(dcm, 'SOPInstanceUID', None)
                
                if sop_instance_uid:
                    output_file = os.path.join(series_dir, f"{sop_instance_uid}.dcm")
                    pydicom.dcmwrite(output_file, dcm, enforce_file_format=True)
                    
                    organized_image_paths[series_uid].append(output_file)
                    
                    if series_uid not in series_to_sop_mapping:
                        series_to_sop_mapping[series_uid] = []
                    series_to_sop_mapping[series_uid].append(sop_instance_uid)
            except Exception as e:
                continue
    
    rtstruct_to_series_mapping = {}
    rtstruct_sop_to_series_mapping = {}
    
    for rtstruct in rtstruct_data:
        referenced_series_uid = rtstruct.get('referenced_series_uid')
        structureset_series_uid = rtstruct.get('structureset_series_uid')
        
        if not referenced_series_uid or not structureset_series_uid:
            continue
        
        series_dir = os.path.join(organized_path, referenced_series_uid)
        if not os.path.exists(series_dir):
            continue
        
        try:
            dcm = pydicom.dcmread(rtstruct['file_path'], force=True)
            rtstruct_sop_uid = getattr(dcm, 'SOPInstanceUID', None)
            
            if rtstruct_sop_uid:
                rtstruct_dir = os.path.join(series_dir, f"RTStruct_{rtstruct_sop_uid}")
                os.makedirs(rtstruct_dir, exist_ok=True)
                
                output_file = os.path.join(rtstruct_dir, f"{rtstruct_sop_uid}.dcm")
                pydicom.dcmwrite(output_file, dcm, enforce_file_format=True)
                
                organized_rtstruct_paths[structureset_series_uid] = output_file
                
                rtstruct_to_series_mapping[structureset_series_uid] = referenced_series_uid
                rtstruct_sop_to_series_mapping[rtstruct_sop_uid] = (referenced_series_uid, rtstruct_dir)
        except Exception as e:
            continue
    
    rtplan_by_sop = {}
    for rtplan in rtplan_data:
        sop_uid = rtplan.get('rtplan_sop_instance_uid')
        if sop_uid:
            rtplan_by_sop[sop_uid] = rtplan
    
    for rtdose in rtdose_data:
        referenced_rtplan_sop = rtdose.get('referenced_rtplan_sop_uid')
        
        if not referenced_rtplan_sop:
            continue
        
        rtplan = rtplan_by_sop.get(referenced_rtplan_sop)
        if not rtplan:
            continue
        
        referenced_structureset_sop = rtplan.get('referenced_structureset_sop_uid')
        if not referenced_structureset_sop:
            continue
        
        if referenced_structureset_sop not in rtstruct_sop_to_series_mapping:
            continue
        
        referenced_series_uid, rtstruct_dir = rtstruct_sop_to_series_mapping[referenced_structureset_sop]
        
        plan_dose_dir = os.path.join(rtstruct_dir, f"Plan_{referenced_rtplan_sop}")
        os.makedirs(plan_dose_dir, exist_ok=True)
        
        try:
            rtplan_dcm = pydicom.dcmread(rtplan['file_path'], force=True)
            rtplan_output = os.path.join(plan_dose_dir, f"RTPLAN_{referenced_rtplan_sop}.dcm")
            pydicom.dcmwrite(rtplan_output, rtplan_dcm, enforce_file_format=True)
            
            rtplan_series_uid = rtplan.get('rtplan_series_uid')
            if rtplan_series_uid:
                organized_rtplan_paths[rtplan_series_uid] = rtplan_output
        except Exception as e:
            continue
        
        try:
            rtdose_dcm = pydicom.dcmread(rtdose['file_path'], force=True)
            rtdose_sop_uid = getattr(rtdose_dcm, 'SOPInstanceUID', 'dose')
            rtdose_output = os.path.join(plan_dose_dir, f"RTDOSE_{rtdose_sop_uid}.dcm")
            pydicom.dcmwrite(rtdose_output, rtdose_dcm, enforce_file_format=True)
            
            rtdose_series_uid = rtdose.get('rtdose_series_uid')
            if rtdose_series_uid:
                organized_rtdose_paths[rtdose_series_uid] = rtdose_output
        except Exception as e:
            continue
    
    return organized_path, organized_image_paths, organized_rtstruct_paths, organized_rtplan_paths, organized_rtdose_paths


def process_training_data_archive(archive_id, extraction_base_path='/tmp/training_data'):
    extraction_path = os.path.join(extraction_base_path, f'archive_{archive_id}')
    os.makedirs(extraction_path, exist_ok=True)
    
    success, result = extract_archive(archive_id, extraction_path)
    if not success:
        return False, f"Failed to extract archive: {result}"
    
    dicom_files = get_all_dicom_files(extraction_path)
    
    if not dicom_files:
        return False, "No files found in the archive"
    
    image_data, rtstruct_data, rtplan_data, rtdose_data = organize_dicom_data(dicom_files)
    
    organized_path, organized_image_paths, organized_rtstruct_paths, organized_rtplan_paths, organized_rtdose_paths = organize_files_by_structure(
        archive_id, image_data, rtstruct_data, rtplan_data, rtdose_data
    )
    
    created_images = save_image_data_to_db(archive_id, image_data, organized_image_paths)
    
    created_rtstructs = save_rtstruct_data_to_db(rtstruct_data, created_images, organized_rtstruct_paths)
    
    save_rtplan_rtdose_data_to_db(rtplan_data, rtdose_data, created_rtstructs, organized_rtplan_paths, organized_rtdose_paths)
    
    return True, {
        'images_count': len(created_images),
        'rtstructs_count': len(created_rtstructs),
        'total_files_processed': len(dicom_files),
        'organized_path': organized_path
    }