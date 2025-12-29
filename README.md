# Individualized Planning Constraints

## Description

This is an application that allows users to upload a set of RTStructureSet files, select the planned prescription dose and get a set of constraints to be used for treatment planning as  well  as for plan evaluation. 


## Workflow

1. User uploads a zip file with DICOM data in the form of planning images and RTStructureSet Files OR uploads it to a folder where the system is configured to look for the data. It also organizes the data into series where each series comprises of the images with the associated RTStructureSet. During this process, the system also ensures that the DICOM files are valid (using Pydicom). 
2. The system then process the DICOM data and extracts information into the respective database model for the app models:
    - Patient information in the Patient model.
    - DICOM Study data in the DICOMStudy model.
    - DICOM Series data in the DICOMSeries model.
    - DICOM Instance data in the DICOMInstance model.
    - RTStructureSet data (for the instance which is a RTStructureSet) in the RTStructureROI model.
    - Image data (for the instances which are images) in the Image information model.

3. It then checks if the structureset ROIs and the DICOM metadata of the dataset match a predefined prescription template. If not then it allows the user to select the correct prescription template. This template matching allows users to map structures to the correct ROIs in the template.

4. Once this is completed, the system then shows the user the individualized dose constraints for the patient. These dose constraints will be derived from predefined constraint templates. The individualized dose constraints will be generated using machine learning.


## Parameters for ML models
The following are the parameters which related to spatial orientation and volume of the target volume and organs at risk:  
1. Volume of the target(s).  
2. Distance of the target(s) from the body surface for external beam radiotherapy plans. For convinience we can measure it as the distance of te centroid of the target to the body surface in the four axes corresponding to the cardinal directions (anterior, posterior, left and right surfaces at the same plane).  
3. Volmetric overlap with the organs at risk for the target(s).  
4. Surface contact of the target(s) with the organs at risk. This surface contact can be measured in terms of the surface area of the target that is in contact with the organs at risk. Additional measures which may be of importance will include the angle of contact in the axial plane and the angle of contact in the sagittal plane. The angles of contact can vary at each of the slices in the axial plane as well as for the reconstructed 3D volume in the sagittal plane. Hence we will need a dimensionality reduction technique to get the angles of contact at each plane into a manageable number of parameters.  We will also need to evaluate methods available in hyperbolic geometry as well as topological sciences for classifying this. The contact plane curvature analysis may be an option also. gaussian and mean curvature analysis may be an option also. Integration of the gaussian curvature ? shape operator
5. Note that there is a special case for SIB target volumes which are often completely encased within a lower dose target volume. In this case, the surface contact is measured as the surface area of the lower dose target volume that is in contact with the SIB target volume.  
