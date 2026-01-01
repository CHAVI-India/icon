from django.db import models
from django.contrib.auth.models import User
from app.models import validate_zip_file

# Create your models here.

   
    


class TrainingDataSetArchive(models.Model):
    '''
    Training data set will be uploaded by the users and will be used to train models. This model will hold information about the zip archive with the training dataset uploaded by the users.  
    '''
    file = models.FileField(upload_to='training_data_set/',validators=[validate_zip_file],help_text="Upload the training data set here.")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE,help_text="User who uploaded the training data set.")
    archive_extracted = models.BooleanField(default=False)
    date_archive_extracted = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Training Data Set File'
        verbose_name_plural = 'Training Data Set Files'
    
    def __str__(self):
        return self.file


class ImageTypeChoices(models.TextChoices):
    CT = 'ct', 'CT'
    MR = 'mr', 'MR'
    PT = 'pt', 'PT'

class TrainingImage(models.Model):

    '''
    This model will store information about the images in the training dataset. All images of a particular modality beloning to a series will be counted and stored in the model. The image paths field will store the paths of all the images in the series.

    '''
    training_data_set_archive = models.ForeignKey(TrainingDataSetArchive, on_delete=models.CASCADE,help_text="Training data set archive to be used for training")
    dicom_series_uid = models.CharField(unique=True,max_length=255, null=True, blank=True,help_text="Image DICOM Series UID")
    number_of_images = models.IntegerField(null=True, blank=True,help_text="Number of images in the series")
    patient_id = models.CharField(max_length=255, null=True, blank=True,help_text="Patient ID")
    series_description = models.CharField(max_length=255, null=True, blank=True,help_text="Series Description")
    series_acquisition_date = models.DateField(null=True, blank=True,help_text="Series Acquisition Date")
    image_type = models.CharField(max_length=255, null=True, blank=True,help_text="Image Type",choices=ImageTypeChoices.choices)
    image_paths = models.JSONField(null=True, blank=True,help_text="Image paths for the series.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Training Image'
        verbose_name_plural = 'Training Images'

    def __str__(self):
        return self.patient_id

class TrainingRTStructureSetFile(models.Model):  
    '''
    This model will store information about the RTStructureSet files in the training dataset.
    '''
    referenced_series_instance_uid = models.ForeignKey(TrainingImage, on_delete=models.CASCADE, max_length=255, help_text="Referenced Series Instance UID. This is obtained from the DICOM file metadata. The UID is available as a nested tag with the following path: Referenced Frame of Reference Sequence > RT Referenced Study Sequence > RT Referenced Series Sequence > Series Instance UID. This UID is also used to link the RTStructureSet file with the corresponding image.")
    structureset_dicom_series_uid = models.CharField(unique=True,max_length=255, null=True, blank=True,help_text="This is the series instance UID of the RTStructureSet File itself.")
    structureset_path = models.CharField(null=True, blank=True,help_text="Path of the RTStructureSet file.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Training Data RTStructureSet'
        verbose_name_plural = 'Training Data RTStructureSets'

    def __str__(self):
        return f"{self.structureset_dicom_series_uid}"


class TrainingRTStructureSetROI(models.Model):  
    '''
    This model will store information about the ROIs in the RTStructureSet files in the training dataset.
    '''
    training_rt_structure_set = models.ForeignKey(TrainingRTStructureSetFile, on_delete=models.CASCADE,help_text="The RT Structure Set to which the ROI belongs to")
    roi_name = models.CharField(max_length=255, null=True, blank=True,help_text="ROI Name")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Training Data RTStructureSet ROI'
        verbose_name_plural = 'Training Data RTStructureSet ROIs'

    def __str__(self):
        return f"{self.roi_name}"

class TrainingRTPlanAndDoseFile(models.Model):
    '''
    This model will store information of the RTPlan and RTDose pair associated with the treatment plan in the training dataset. The RTPlan and RTDose for a given structureset are linked to each other by the Referenced RT Plan Sequence > Referenced SOP Instance UID tag in the RTDose File.
    '''
    structureset_referenced_series_intance_uid = models.ForeignKey(TrainingRTStructureSetFile, on_delete=models.CASCADE,help_text="The RT Structure Set to which the RT Plan and Dose belong to. This information is available in the Referenced Structure Set Sequence > Referenced SOP Instance UID.")
    rtdose_series_instance_uid  = models.CharField(max_length=255, help_text = "Series Instance UID of the RTDose file.")
    rtdose_path = models.CharField(null=True, blank=True,help_text="Path of the RTDose file.")
    rtplan_series_instance_uid = models.CharField(max_length=255, help_text = "Series Instance UID of the RTPlan file.")
    rtplan_path = models.CharField(null=True, blank=True,help_text="Path of the RTPlan file.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Training Data RTPlan and RTDose Pair'
        verbose_name_plural = 'Training Data RTPlan and RTDose Pairs'
    
    def __str__(self):
        return f"{self.rtdose_series_instance_uid} - {self.rtplan_series_instance_uid}"
