from email.policy import default
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import magic
import zipfile
import os
# Create your models here.

## File handling model

class ProcessingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'

def validate_zip_file(file):
    """
    Validator function to ensure uploaded file is a valid ZIP file.
    Performs both extension check and MIME type detection.
    """
    # Check file extension
    file_extension = os.path.splitext(file.name)[1].lower()
    if file_extension != '.zip':
        raise ValidationError(
            f'Invalid file extension "{file_extension}". Only .zip files are allowed.'
        )
    
    # Check MIME type using python-magic
    try:
        # Read the first chunk of the file for MIME type detection
        file.seek(0)
        file_mime = magic.from_buffer(file.read(2048), mime=True)
        file.seek(0)  # Reset file pointer
        
        # Valid MIME types for ZIP files
        valid_mime_types = [
            'application/zip',
            'application/x-zip-compressed',
            'multipart/x-zip'
        ]
        
        if file_mime not in valid_mime_types:
            raise ValidationError(
                f'Invalid file type. Detected MIME type: "{file_mime}". '
                f'Expected a ZIP file with MIME type: {" or ".join(valid_mime_types)}.'
            )
    except Exception as e:
        raise ValidationError(f'Error detecting file type: {str(e)}')
    
    # Verify the file is a valid ZIP archive
    try:
        file.seek(0)
        # Try to open as a ZIP file to verify integrity
        zip_file = zipfile.ZipFile(file)
        # Test the ZIP file for errors
        bad_file = zip_file.testzip()
        if bad_file:
            raise ValidationError(
                f'Corrupted ZIP file. File "{bad_file}" failed integrity check.'
            )
        zip_file.close()
        file.seek(0)  # Reset file pointer
    except zipfile.BadZipFile:
        raise ValidationError('Invalid or corrupted ZIP file.')
    except Exception as e:
        raise ValidationError(f'Error validating ZIP file: {str(e)}')

class DICOMFile(models.Model):
    '''
    Model to store information about the DICOM file uploaded by the user. This model also stores information about the processing done for the DICOM files in the archive.
    '''
    file = models.FileField(
        upload_to='dicom_files',
        help_text="Upload the DICOM file here.",
        validators=[validate_zip_file]
    )
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE,help_text="User who uploaded the DICOM file. Please upload a single ZIP file.")
    processing_status = models.CharField(max_length=255, default=ProcessingStatus.PENDING, choices=ProcessingStatus.choices,help_text="Processing status of the DICOM file.")
    date_processing_completed = models.DateTimeField(null=True, blank=True,help_text="Date and time when the processing is completed successfully.")
    processing_log_data = models.JSONField(null=True, blank=True,help_text="Processing log data stored after processing is completed.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "DICOM Files"
    
    def __str__(self):
        return self.file.name

## Rules related models

class RuleGroup(models.Model):
    '''
    Model to store information on the rulegroup to be used for matching the RTStructureSet with the Prescription template. Each rule group has multiple rulesets that can be evaluated together.
    '''
    rulegroup_name = models.CharField(max_length=255, unique=True,help_text="Name of the rulegroup")
    rulegroup_description = models.TextField(null=True, blank=True,help_text="Description of the rulegroup")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Rule Groups"
    
    def __str__(self):
        return self.rulegroup_name

class CombinationChoices(models.TextChoices):
    AND = 'and', 'And'
    OR = 'or', 'Or'

class Ruleset(models.Model):
    '''
    Model to store information on the ruleset to be used for matching the RTStructureSet with the Prescription template. Each ruleset belongs to a rulegroup.
    '''
    rulegroup = models.ForeignKey(RuleGroup, on_delete=models.CASCADE,help_text="Rulegroup to which the ruleset belongs to")
    ruleset_order = models.PositiveIntegerField(help_text="Order of the ruleset. Rulesets will be evaluated in the numerical order specified with lower value numbers being evaluated first.")
    ruleset_name = models.CharField(max_length=255, unique=True,help_text="Name of the ruleset")
    ruleset_combination = models.CharField(max_length=255, null=True, blank=True,help_text="Defines how this ruleset should be combined with the other rulesets in the same rulegroup")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Rule Sets"
        constraints = [
            models.UniqueConstraint(
                fields=['rulegroup', 'ruleset_order'],
                name='unique_rulegroup_ruleset_order'
            )
        ]
    
    def __str__(self):
        return self.ruleset_name

class ParameterToBeMatchedChoices(models.TextChoices):
    ROINAME = 'roi_name', 'ROI Name'
    MODALITY = 'modality', 'Modality'
    STRUCTURESETLABEL = 'structure_set_label', 'Structure Set Label'
    STUDY_DESCRIPTION = 'study_description', 'Study Description'
    SERIES_DESCRIPTION = 'series_description', 'Series Description'
    PATIENT_SEX = 'patients_sex', "Patient's Sex"
    APPROVAL_STATUS = 'approval_status', 'Approval Status'
    
class MatchingOperatorChoices(models.TextChoices):
    EQUALS = 'equals', 'Equals'
    NOT_EQUALS = 'not_equals', 'Not Equals'
    STRING_CONTAINS_CASE_INSENSITIVE = 'string_contains_case_insensitive', 'String Contains Case Insensitive'
    STRING_CONTAINS_CASE_SENSITIVE = 'string_contains_case_sensitive', 'String Contains Case Sensitive'
    STRING_DOES_NOT_CONTAIN_CASE_INSENSITIVE = 'string_does_not_contain_case_insensitive', 'String Does Not Contain Case Insensitive'
    STRING_DOES_NOT_CONTAIN_CASE_SENSITIVE = 'string_does_not_contain_case_sensitive', 'String Does Not Contain Case Sensitive'
    GREATER_THAN = 'greater_than', 'Greater Than'
    GREATER_THAN_OR_EQUAL_TO = 'greater_than_or_equal_to', 'Greater Than Or Equal To'
    LESS_THAN = 'less_than', 'Less Than'
    LESS_THAN_OR_EQUAL_TO = 'less_than_or_equal_to', 'Less Than Or Equal To'

class Rule(models.Model):
    '''
    Defines individual rules to be used to be used in a ruleset. A ruleset may have multiple rules. Each rule is evaluated in the order specified inside a ruleset. If all rules match then the ruleset is supposed to match.
    '''
    ruleset = models.ForeignKey(Ruleset, on_delete=models.CASCADE,help_text="Ruleset to which the rule belongs to")
    rule_order = models.PositiveIntegerField(help_text="Order of the rule. Rules will be evaluated in the numerical order specified with lower value numbers being evaluated first.")
    parameter_to_be_matched = models.CharField(max_length=255, null=True, blank=True,help_text="Parameter to be matched. Select from the list or provide your own",choices=ParameterToBeMatchedChoices.choices)
    matching_operator = models.CharField(max_length=255, null=True, blank=True,help_text="Matching operator to be used. Select from the list or provide your own",choices=MatchingOperatorChoices.choices)
    matching_value = models.CharField(max_length=255, null=True, blank=True,help_text="Matching value to be used for the matching")
    rule_combination_type = models.CharField(max_length=255, null=True, blank=True,help_text="How should the rule be combined with other rules in the ruleset.",choices=CombinationChoices.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Rules"
        constraints = [
            models.UniqueConstraint(
                fields=['ruleset', 'rule_order'],
                name='unique_ruleset_rule_order'
            )
        ]
    
    def __str__(self):
        return self.parameter_to_be_matched + " " + self.matching_operator + " " + self.matching_value


## Prescription Template related models 
class CancerSideChoices(models.TextChoices):
    LEFT = 'left', 'Left'
    RIGHT = 'right', 'Right'
    MIDLINE = 'midline', 'Midline'
    BILATERAL = 'bilateral', 'Bilateral'
    NOT_APPLICABLE = 'not_applicable', 'Not Applicable'

class TreatmentModalityChoices(models.TextChoices):
    EBRT = 'EBRT', 'External Beam Radiotherapy'
    ELECTRON = 'Electron', 'Electron'
    PROTON = 'Proton', 'Proton'
    CARBON = 'Carbon', 'Carbon Ion'
    BRACHYTHERAPY = 'Brachytherapy', 'Brachytherapy'
 
class PrescriptionTemplate(models.Model):
    '''
    Model to store information about the prescription template. This data will include the information about the prescription template name, cancer site and the side of treatment. It will also include information about the treatment modality, beam energy to be used.
    '''
    name = models.CharField(max_length=255, unique=True,help_text="Name of the prescription template")
    cancer_site = models.CharField(max_length=255, null=True, blank=True,help_text="Cancer site. Select from the list or provide your own")
    cancer_side = models.CharField(max_length=255, null=True, blank=True,help_text="Side of the disease. Select from the list.",choices=CancerSideChoices.choices)
    treatment_modality = models.CharField(max_length=255, null=True, blank=True,help_text="Treatment modality. Select from the list.",choices=TreatmentModalityChoices.choices)
    ebrt_beam_energy = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Beam energy to be used in MV for EBRT")
    electron_beam_energy = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Beam energy to be used in MeV for Electron Therapy")
    proton_beam_energy = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Beam energy to be used in MeV for Proton Therapy")  
    carbon_beam_energy = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="Beam energy to be used in MeV for Carbon Ion Therapy")
    rulegroup_name = models.OneToOneField(RuleGroup, on_delete=models.CASCADE,help_text="Rulegroup to which the prescription template belongs to")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Prescription Template"
    
    def clean(self):
        super().clean()
        errors = {}
        
        # Validate that the appropriate beam energy is provided for the selected modality
        if self.treatment_modality == TreatmentModalityChoices.EBRT:
            if not self.ebrt_beam_energy:
                errors['ebrt_beam_energy'] = 'EBRT beam energy is required when treatment modality is EBRT.'
            # Ensure other modality energies are not provided
            if self.electron_beam_energy:
                errors['electron_beam_energy'] = 'Electron beam energy should not be provided when treatment modality is EBRT.'
            if self.proton_beam_energy:
                errors['proton_beam_energy'] = 'Proton beam energy should not be provided when treatment modality is EBRT.'
            if self.carbon_beam_energy:
                errors['carbon_beam_energy'] = 'Carbon beam energy should not be provided when treatment modality is EBRT.'
                
        elif self.treatment_modality == TreatmentModalityChoices.ELECTRON:
            if not self.electron_beam_energy:
                errors['electron_beam_energy'] = 'Electron beam energy is required when treatment modality is Electron.'
            # Ensure other modality energies are not provided
            if self.ebrt_beam_energy:
                errors['ebrt_beam_energy'] = 'EBRT beam energy should not be provided when treatment modality is Electron.'
            if self.proton_beam_energy:
                errors['proton_beam_energy'] = 'Proton beam energy should not be provided when treatment modality is Electron.'
            if self.carbon_beam_energy:
                errors['carbon_beam_energy'] = 'Carbon beam energy should not be provided when treatment modality is Electron.'
                
        elif self.treatment_modality == TreatmentModalityChoices.PROTON:
            if not self.proton_beam_energy:
                errors['proton_beam_energy'] = 'Proton beam energy is required when treatment modality is Proton.'
            # Ensure other modality energies are not provided
            if self.ebrt_beam_energy:
                errors['ebrt_beam_energy'] = 'EBRT beam energy should not be provided when treatment modality is Proton.'
            if self.electron_beam_energy:
                errors['electron_beam_energy'] = 'Electron beam energy should not be provided when treatment modality is Proton.'
            if self.carbon_beam_energy:
                errors['carbon_beam_energy'] = 'Carbon beam energy should not be provided when treatment modality is Proton.'
                
        elif self.treatment_modality == TreatmentModalityChoices.CARBON:
            if not self.carbon_beam_energy:
                errors['carbon_beam_energy'] = 'Carbon beam energy is required when treatment modality is Carbon Ion.'
            # Ensure other modality energies are not provided
            if self.ebrt_beam_energy:
                errors['ebrt_beam_energy'] = 'EBRT beam energy should not be provided when treatment modality is Carbon Ion.'
            if self.electron_beam_energy:
                errors['electron_beam_energy'] = 'Electron beam energy should not be provided when treatment modality is Carbon Ion.'
            if self.proton_beam_energy:
                errors['proton_beam_energy'] = 'Proton beam energy should not be provided when treatment modality is Carbon Ion.'
                
        elif self.treatment_modality == TreatmentModalityChoices.BRACHYTHERAPY:
            # Brachytherapy doesn't require beam energy, ensure none are provided
            if self.ebrt_beam_energy:
                errors['ebrt_beam_energy'] = 'EBRT beam energy should not be provided when treatment modality is Brachytherapy.'
            if self.electron_beam_energy:
                errors['electron_beam_energy'] = 'Electron beam energy should not be provided when treatment modality is Brachytherapy.'
            if self.proton_beam_energy:
                errors['proton_beam_energy'] = 'Proton beam energy should not be provided when treatment modality is Brachytherapy.'
            if self.carbon_beam_energy:
                errors['carbon_beam_energy'] = 'Carbon beam energy should not be provided when treatment modality is Brachytherapy.'
                
        elif self.treatment_modality:
            errors['treatment_modality'] = 'Invalid treatment modality selected.'
        
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.name

class DoseUnitChoice(models.TextChoices):
    Gy = 'Gy', 'Gy'
    cGy = 'cGy', 'cGy'

class Prescription(models.Model):
    '''
    Model to store information about the dose prescription for a given volume associated with a template. We ensure that each prescription template can have a single prescription for a given ROI. Note that the dose unit is specified here so that constraints can be generated as per the unit specified.
    '''
    prescription_template = models.ForeignKey(PrescriptionTemplate, on_delete=models.CASCADE,help_text="Prescription Template ID to which the prescription belongs to")
    roi_name = models.CharField(max_length=255,help_text="ROI Name to be matched to RTStructureSet")
    dose_prescribed = models.DecimalField(max_digits=7, decimal_places=3, help_text="Dose prescribed")
    dose_unit = models.CharField(max_length=10, choices=DoseUnitChoice.choices, default=DoseUnitChoice.Gy)
    fractions_prescribed = models.IntegerField(help_text="Number of fractions prescribed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Prescriptions"
        constraints = [
            models.UniqueConstraint(
                fields=['prescription_template_id', 'roi_name'],
                name='unique_prescription_template_roi_name'
            )
        ]

    def clean(self):
        super().clean()
        # Validate if the prescription dose is greater than 0
        if self.dose_prescribed <= 0:
            raise ValidationError({'dose_prescribed': 'Dose prescribed must be greater than 0.'})
        # Validate if the prescription fractions is greater than 0
        if self.fractions_prescribed <= 0:
            raise ValidationError({'fractions_prescribed': 'Fractions prescribed must be greater than 0.'})    
    
    def __str__(self):
        return self.roi_name    


## DICOM data related models

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
        return f"{self.patient_name} ({self.unique_patient_id})"

class DICOMStudy(models.Model):
    '''
    Model to store information about study from the DICOM data.
    '''
    study_instance_uid = models.CharField(max_length=255, unique=True,help_text="DICOM Study Instance UID extracted from the DICOM data.")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE,help_text="Patient ID to which the DICOM study refers to.")
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
    dicom_study = models.ForeignKey(DICOMStudy, on_delete=models.CASCADE,help_text="DICOM Study ID to which the DICOM series refers to.")
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
    sop_instance_uid = models.CharField(max_length = 255, unique=True,help_text="DICOM SOP Instance UID extracted from the DICOM data.")
    dicom_series = models.ForeignKey(DICOMSeries, on_delete=models.CASCADE,help_text="DICOM Series ID to which the DICOM instance refers to.")
    modality = models.CharField(max_length=10, null=True, blank=True,help_text="Modality tag data extracted from the DICOM data")
    pixel_spacing = models.CharField(max_length=255, null=True, blank=True,help_text="Pixel Spacing tag data extracted from the DICOM data")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "DICOM Instances"
    
    def __str__(self):
        return self.sop_instance_uid

class ImageInformation(models.Model):
    '''
    This model will store information about the individual images in the DICOM dataset if the modality is a CT/MRI/PET. The information stored will include information about the 
    slice location, pixel spacing, slice thickness, patient_position, Image Position (Patient), Image Orientation (Patient),Instance Number. Note that the model uses a one to one relationship between the instance and the image information as one instance can only have one image information.
    '''
    dicom_instance = models.OneToOneField(DICOMInstance,on_delete=models.CASCADE,help_text="The DICOM Instance ID of the image referenced.")
    slice_location = models.DecimalField(null=True,blank=True,help_text="The Slice Location value extracted from the DICOM data",decimal_places=5,max_digits=15)
    pixel_spacing = models.JSONField(null=True,blank=True, help_text = "Pixel spacing value obtained from the DICOM file. The two values represent the distance between the center of the pixels in the row and column respectively.")
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
        return f"ImageInformation {self.id}"

class RTStructureSetInformation(models.Model):
    '''
    Model to store information about the RTStructureSet file. This information will include the reference to the dicom instance to which the RTStructureSet file refers to.
    '''
    dicom_instance = models.OneToOneField(DICOMInstance, on_delete=models.CASCADE,help_text="DICOM Instance ID for the ROI obtained from the RTStructureSet data")
    number_of_roi = models.IntegerField(null=True, blank=True,help_text="Number of ROIs in the RTStructureSet")
    referenced_frame_of_reference_uid = models.CharField(max_length=255, null=True, blank=True,help_text="Referenced Frame of Reference UID tag data extracted from the RTStructureSet data")
    prescription_template_id = models.ForeignKey(PrescriptionTemplate, on_delete=models.CASCADE,help_text="Prescription Template ID to which the RTStructureSet belongs to",null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "RT Structure Set Information"

    def __str__(self):
        return f"RTStructureSetInformation {self.id}"

class RTStructureROI(models.Model):

    '''
    Model to store information about volumes of interest (VOIs) from the RTStructureSet File. This data will include the information about the contour points for the specific ROI. Contour point information will be stored in the JSON field and used to reconstruct the contour array.
    '''
    rt_structure_set = models.ForeignKey(RTStructureSetInformation, on_delete=models.CASCADE,help_text="RTStructureSet Information ID for the ROI obtained from the RTStructureSet data")
    roi_number = models.IntegerField(help_text="ROI Number tag data extracted from the RTStructureSet data")
    roi_name = models.CharField(max_length=255, help_text="ROI Name tag data extracted from the RTStructureSet data")
    roi_contour_data = models.JSONField(help_text="ROI Contour Data tag data extracted from the RTStructureSet data along with corresponding Referenced SOP Instance UID values for each Referenced SOP Instance UID. This will be stored as a tuple.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "RT Structure Regions of Interest"

    def __str__(self):
        return f"RTStructureROI {self.id}"



    







    




    
    