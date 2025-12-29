from django.db import models

# Create your models here.

class GenderChoices(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'
    OTHER = 'other', 'Other'

class Patient(models.Model):
    '''
    Model to store information about patient from the DICOM data.
    '''
    unique_patient_id = models.CharField(max_length=255, unique=True,help_text="Unique Patient ID extracted from DICOM data")
    patient_name = models.CharField(max_length=255, null=True, blank=True, help_text="Patient Name extracted from DICOM data")
    patient_dob = models.DateField(null=True, blank=True, help_text="Patient DOB extracted from DICOM data")
    patient_sex = models.CharField(max_length=10, null=True, blank=True, choices=GenderChoices.choices, help_text="Patient Sex extracted from DICOM data. This is then matched to the Gender choices")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Patients"

    def __str__(self):
        return self.patient_name


class DICOMStudy(models.Model):
    '''
    Model to store information about study from the DICOM data.
    '''
    study_instance_uid = models.CharField(max_length=255, unique=True,help_text="DICOM Study Instance UID extracted from the DICOM data.")
    patient_id = models.ForeignKey(Patient, on_delete=models.CASCADE,help_text="Patient ID to which the DICOM study refers to.")
    study_description = models.CharField(max_length=255, null=True, blank=True,help_text="Study Description tag data extracted from the DICOM data")
    study_date = models.DateField(null=True, blank=True,help_text="Study Date tag data extracted from the DICOM data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "DICOM Studies"
    
    def __str__(self):
        return self.study_instance_uid


class DICOMSeries(models.Model):
    '''
    Model to store information about series from the DICOM data.
    '''
    series_instance_uid = models.CharField(max_length=255, unique=True,help_text="DICOM Series Instance UID extracted from the DICOM data.")
    frame_of_reference_uid = models.CharField(max_length=255, null=True, blank=True,help_text="Frame of Reference UID extracted from the DICOM data.")
    dicom_study_id = models.ForeignKey(DICOMStudy, on_delete=models.CASCADE,help_text="DICOM Study ID to which the DICOM series refers to.")
    series_description = models.CharField(max_length=255, null=True, blank=True,help_text="Series Description tag data extracted from the DICOM data")
    series_date = models.DateField(null=True, blank=True,help_text="Series Date tag data extracted from the DICOM data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        verbose_name_plural = "DICOM Series"
    
    def __str__(self):
        return self.series_instance_uid


class DICOMInstance(models.Model):
    '''
    Model to store information about instance from the DICOM data.
    '''
    sop_intance_uid = models.CharField(max_length = 255, unique=True,help_text="DICOM SOP Instance UID extracted from the DICOM data.")
    dicom_series_id = models.ForeignKey(DICOMSeries, on_delete=models.CASCADE,help_text="DICOM Series ID to which the DICOM instance refers to.")
    modality = models.CharField(max_length=10, null=True, blank=True,help_text="Modality tag data extracted from the DICOM data")
    pixel_spacing = models.CharField(max_length=255, null=True, blank=True,help_text="Pixel Spacing tag data extracted from the DICOM data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "DICOM Instances"
    
    def __str__(self):
        return self.sop_intance_uid


class ImageInformation(models.Model):
    '''
    This model will store information about the individual images in the DICOM dataset if the modality is a CT/MRI/PET. The information stored will include information about the 
    slice location, pixel spacing, slice thickness, patient_position, Image Position (Patient), Image Orientation (Patient),Instance Number.
    '''
    dicom_instance_id = models.ForeignKey(DICOMInstance,on_delete=models.CASCADE,help_text="The DICOM Instance ID of the image referenced.")
    slice_location = models.IntegerField(null=True,blank=True,help_text="The Slice Location value extracted from the DICOM data")
    pixel_spacing = models.DecimalField(null=True,blank=True, help_text = "Pixel spacing value obtained from the DICOM file",decimal_places=5,max_digits=15)
    slice_thickness = models.DecimalField(null=True,blank=True,help_text="Slice thickness values obtained from the DICOM file",decimal_places=5,max_digits=15)
    patient_position = models.CharField(max_length=255, null=True, blank=True,help_text="Patient Position tag data extracted from the DICOM data")
    image_position_patient = models.JSONField(null=True, blank=True,help_text="Image Position (Patient) tag data extracted from the DICOM data. It refers to the x, y, and z coordinates of the upper left hand corner of the image; it is the center of the first voxel transmitted")
    image_orientation_patient = models.JSONField(null=True, blank=True,help_text="Image Orientation (Patient) tag data extracted from the DICOM data. It specifies the direction cosines of the first row and the first column with respect to the patient. These Attributes shall be provide as a pair. Row value for the x, y, and z axes respectively followed by the Column value for the x, y, and z axes respectively.")
    instance_number = models.IntegerField(null=True,blank=True,help_text="Instance Number tag data extracted from the DICOM data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Image Information"

    def __str__(self):
        return self.dicom_instance_id


class RTStructureROI(models.Model):

    '''
    Model to store information about volumes of interest (VOIs) from the RTStructureSet Data. This data will include the information about the contour points for the specific ROI. Additionally it will also store information about the Referenced SOP instance UID. This information will be stored in the JSON field and used to reconstruct the array.
    '''
    dicom_instance_id = models.ForeignKey(DICOMInstance, on_delete=models.CASCADE,help_text="DICOM Instance ID for the ROI obtained from the RTStructureSet data")
    roi_number = models.IntegerField(null=True, blank=True,help_text="ROI Number tag data extracted from the RTStructureSet data")
    roi_name = models.CharField(max_length=255, null=True, blank=True,help_text="ROI Name tag data extracted from the RTStructureSet data")
    referenced_frame_of_reference_uid = models.CharField(max_length=255, null=True, blank=True,help_text="Referenced Frame of Reference UID tag data extracted from the RTStructureSet data")
    roi_contour_point_sequence = models.JSONField(help_text="ROI Contour Point Sequence tag data extracted from the RTStructureSet data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "RT Structure Regions of Interest"

    def __str__(self):
        return self.roi_name












    




    
    